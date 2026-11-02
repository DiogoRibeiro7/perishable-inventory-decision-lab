# Run from studies/orange_storage_decision:
# Rscript scripts/run_inspection_plan_value.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shape_ensemble.R")
source("R/inspection_removals.R")
source("R/inspection_plan_value.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) stop("usage: run_inspection_plan_value.R [number_of_lots] [output_directory]")
n_lots <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) == 2L) args[2] else "results/inspection_plan_value"
settings <- list(n_lots = n_lots, metadata_seed = 20261110L, fruit_seed = 20261111L,
  sampling_seed = 20261112L, bootstrap_seed = 9215L, n_boot = 1000L,
  budgets = c(30L, 90L, 180L), training_days = c(3L, 6L, 9L, 12L),
  costs = c(0, 0.02, 0.05, 0.10), fruit_mass_kg = 0.20,
  sensitivity = 0.9, specificity = 0.9, decision_day = 12L, last_sale_day = 28L,
  no_inspection_sale_days = c(12L, 16L), delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, r_version = R.version.string, rng_kind = RNGkind())
records <- run_plan_value_experiment(n_lots, settings$metadata_seed, settings$fruit_seed, settings$sampling_seed)
set.seed(settings$bootstrap_seed)
summary <- summarize_plan_value(records, settings$costs, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"), file.path(destination, "settings.R"), useBytes = TRUE)

paid <- summary[summary$labour_eur_per_check == 0.02, ]
free <- summary[summary$labour_eur_per_check == 0, ]
lines <- c("# Does destructive inspection pay for itself?", "",
  sprintf("%d fresh independent synthetic lots, three prespecified plans, and the same finite fruit population for all alternatives.", n_lots),
  "Every lot starts with 850 kg of eligible fruit (4,250 fruit at 0.20 kg).",
  "Plans inspect 30, 90 or 180 fruit per stratum on days 3/6/9/12, removing",
  "48, 144 or 288 kg respectively. Every inspected fruit is destroyed, regardless",
  "of its reported quality. No-inspection comparators retain the full inventory.", "",
  "Inspection-driven dates use the same fixed AIC-mixture policy on remaining",
  "inventory. Benchmarks sell without inspection on prespecified days 12 or 16.",
  "All returns include physical holding costs from harvest through delivery,",
  "including savings from earlier removals. Sale before day 12 is outside this study.", "",
  "## Returns at hypothetical EUR 0.02 per check", "",
  sprintf("Mean no-inspection returns are EUR %.2f at day 12 and EUR %.2f at day 16.",
    paid$mean_no_inspection_day12_eur[1], paid$mean_no_inspection_day16_eur[1]), "",
  "| Checks/stratum/day | Total checks | Mean sale day | Mean net EUR | Gain vs no-inspection day 12 [95% CI] | Gain vs no-inspection day 16 [95% CI] | Below day 12 / day 16 |",
  "|---|---:|---:|---:|---:|---:|---:|")
for (i in seq_len(nrow(paid))) {
  x <- paid[i, ]
  lines <- c(lines, sprintf("| %d | %d | %.2f | %.2f | %+.2f [%+.2f, %+.2f] | %+.2f [%+.2f, %+.2f] | %.1f%% / %.1f%% |",
    x$per_group, x$inspection_count, x$mean_sale_day, x$mean_net_return_eur,
    x$gain_vs_day12_eur_mean, x$gain_vs_day12_eur_lower_95, x$gain_vs_day12_eur_upper_95,
    x$gain_vs_day16_eur_mean, x$gain_vs_day16_eur_lower_95, x$gain_vs_day16_eur_upper_95,
    100 * x$below_day12_fraction, 100 * x$below_day16_fraction))
}
lines <- c(lines, "", "## Where the difference comes from", "",
  "The following identity holds for every lot: gain versus no-inspection day 12",
  "equals the timing gain on remaining fruit minus net removal cost minus labour.",
  "Timing gain compares the chosen date with day 12 after the same removals.",
  "Net removal cost is the removed fruit's forgone day-12 sale revenue, less its",
  "saved holding cost through delivery. It can be negative and is never clipped.", "",
  "| Checks/stratum/day | Timing gain EUR | Net removal cost EUR | Labour EUR | Total gain EUR |",
  "|---|---:|---:|---:|---:|")
for (i in seq_len(nrow(paid))) {
  x <- paid[i, ]
  lines <- c(lines, sprintf("| %d | %+.2f | %.2f | %.2f | %+.2f |", x$per_group,
    x$timing_gain_eur_mean, x$removal_net_cost_eur_mean, x$mean_labour_eur, x$gain_vs_day12_eur_mean))
}
lines <- c(lines, "", "## Labour sensitivity and break-even charges", "",
  "Policies and fruit outcomes stay fixed at every labour price. The break-even",
  "charge is the mean gain before labour divided by the number of checks.",
  "A negative value means free labour still fails to cover the net removal cost",
  "relative to day-12 sale without inspection; it is not a feasible positive price.", "",
  "| Checks/stratum/day | Gain with free labour EUR [95% CI] | Break-even EUR/check [95% CI] |",
  "|---|---:|---:|")
for (i in seq_len(nrow(free))) {
  x <- free[i, ]
  lines <- c(lines, sprintf("| %d | %+.2f [%+.2f, %+.2f] | %+.4f [%+.4f, %+.4f] |", x$per_group,
    x$gain_vs_day12_eur_mean, x$gain_vs_day12_eur_lower_95, x$gain_vs_day12_eur_upper_95,
    x$break_even_labour_vs_day12_mean, x$break_even_labour_vs_day12_lower_95, x$break_even_labour_vs_day12_upper_95))
}
lines <- c(lines, "", "![Inspection plan returns](inspection_plan_value.png)", "",
  "## Interpretation and reproduction", "",
  "These are paired policy comparisons under one synthetic nearby-shape regime,",
  "not an estimate of the optimal value of information. Random sample IDs are",
  "disjoint across days and nested across plans. Hidden lifetimes supply only",
  "pre-cutoff inspection labels to fitting; raw IDs, future outcomes and true",
  "parameters never enter policy fitting. Evaluation uses actual uninspected fruit.", "",
  "Intervals resample independent whole lots, not fruit or the three correlated",
  "plan records as independent observations. They are marginal percentile 95%",
  "intervals without multiple-comparison adjustment. Costs and sample plans were",
  "fixed before outcomes; no winning plan is selected on these evaluation lots.", "",
  "Known prices and grading accuracy, independent equal-mass fruit, no handling",
  "damage or disposal value, fixed inspection days and fixed sale benchmarks limit",
  "interpretation. Historical-data policies, earlier sales, other inspection",
  "designs and empirically measured costs could change the comparison.", "",
  "```sh", sprintf("Rscript scripts/run_inspection_plan_value.R %d", n_lots), "```", "",
  "[Records](records.csv), [summary](summary.csv), [settings](settings.R),",
  "and [protocol](../../INSPECTION_PLAN_VALUE.md) preserve the assumptions and results.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "inspection_plan_value.png"), width = 1500, height = 820, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 5, 4, 1), mgp = c(3.5, 1, 0))
graphics::plot(1:3, paid$gain_vs_day12_eur_mean, pch = 19, col = "#276a98", xaxt = "n", las = 1,
  xlim = c(0.6, 3.4), ylim = range(c(0, paid$gain_vs_day12_eur_lower_95, paid$gain_vs_day12_eur_upper_95)),
  xlab = "Checks per stratum/day", ylab = "Mean gain versus no-inspection day 12 (EUR)",
  main = "Whole-plan return at EUR 0.02/check")
graphics::mtext("Paired whole-lot 95% bootstrap intervals", side = 3, line = 0.4, cex = 0.75)
graphics::axis(1, at = 1:3, labels = paid$per_group)
graphics::abline(h = 0, lty = 2, col = "grey50")
graphics::arrows(1:3, paid$gain_vs_day12_eur_lower_95, 1:3, paid$gain_vs_day12_eur_upper_95,
  code = 3, angle = 90, length = 0.06, col = "#276a98")
components <- rbind(paid$timing_gain_eur_mean, -paid$removal_net_cost_eur_mean, -paid$mean_labour_eur)
graphics::barplot(components, beside = TRUE, names.arg = paid$per_group,
  col = c("#276a98", "#b95445", "#c5a54b"), border = NA, las = 1,
  ylim = range(c(0, components)) * 1.25, xlab = "Checks per stratum/day", ylab = "Mean contribution (EUR)",
  main = "Timing, removals and labour")
graphics::abline(h = 0, col = "grey50")
graphics::legend("bottomleft", legend = c("Timing gain", "Minus net removal cost", "Minus labour"),
  fill = c("#276a98", "#b95445", "#c5a54b"), bty = "n", cex = 0.75)
invisible(grDevices::dev.off())
cat(sprintf("Wrote %d paired plan records to %s\n", nrow(records), destination))
