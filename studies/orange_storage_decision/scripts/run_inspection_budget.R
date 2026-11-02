# Run from studies/orange_storage_decision:
# Rscript scripts/run_inspection_budget.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shared_shape_evaluation.R")
source("R/shape_ensemble.R")
source("R/inspection_budget.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) stop("usage: run_inspection_budget.R [number_of_lots] [output_directory]")
n_lots <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) == 2L) args[2] else "results/inspection_budget"
settings <- list(n_lots = n_lots, training_seed = 20261106L, outcome_seed = 20261107L,
  bootstrap_seed = 9213L, n_boot = 1000L, budgets = c(30L, 90L, 180L),
  costs_eur_per_inspection = c(0, 0.02, 0.05, 0.10), sensitivity = 0.9, specificity = 0.9,
  decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, training_days = c(3L, 6L, 9L, 12L), holdout_per_group = 250L,
  scenarios = default_shape_scenarios(), r_version = R.version.string, rng_kind = RNGkind())
records <- run_inspection_budget_experiment(n_lots, settings$training_seed,
  settings$outcome_seed, settings$budgets, settings$scenarios)
summary <- summarize_inspection_budgets(records, settings$costs_eur_per_inspection)
set.seed(settings$bootstrap_seed)
contrasts <- compare_inspection_budgets(records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
utils::write.csv(contrasts, file.path(destination, "contrasts.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"),
  file.path(destination, "settings.R"), useBytes = TRUE)

lines <- c("# How much are additional inspections worth?", "",
  sprintf("%d independent base lots, three shape regimes, and three fixed inspection plans.", n_lots),
  "Plans inspect 30, 90 or 180 fruit per stratum on days 3/6/9/12:",
  "240, 720 or 1,440 inspections per lot. All plans share inventory, prices,",
  "training uniforms and future outcomes. Inspection calibration is known (Se=Sp=0.9).", "",
  "Models and decision rules are fixed before the study. The ensemble averages",
  "separate/shared-shape predictions using training-only AIC weights.",
  "The standalone separate and shared models are also evaluated.", "",
  "## Ensemble prediction and economic performance", "",
  "Sale return is EUR after storage and delivery rejection, before inspection charges.",
  "Net advantage subtracts all inspection charges and compares with day-12 immediate",
  "sale, which requires no inspections. EUR 0.02 per check is hypothetical, not a market estimate.", "",
  "| Shape regime | Checks per stratum/day | Total checks | Brier | Log loss | Sale return | Net advantage at EUR 0.02/check | Below immediate at EUR 0.02/check |",
  "|---|---:|---:|---:|---:|---:|---:|---:|")
shown <- subset(summary, model == "ensemble" & cost_eur_per_inspection == 0.02)
shown <- shown[order(shown$scenario, shown$per_group), ]
for (i in seq_len(nrow(shown))) {
  x <- shown[i, ]
  lines <- c(lines, sprintf("| %s | %d | %d | %.4f | %.4f | %.2f | %+.2f | %.1f%% |",
    x$scenario, x$per_group, x$inspection_count, x$mean_brier, x$mean_log_loss,
    x$mean_sale_return_eur, x$mean_net_minus_immediate_eur, 100 * x$below_immediate_fraction))
}
lines <- c(lines, "", "## Paired benefit and break-even inspection price", "",
  "Each row compares a larger plan with 30 checks per stratum/day, under the same model.",
  "Gain excludes inspection charges. Break-even EUR per extra check is mean gain",
  "divided by the additional number of checks (480 or 1,200). Intervals are marginal",
  "95% paired whole-lot bootstrap intervals; negative thresholds are retained.", "",
  "| Regime | Model | Larger plan | Sale-return gain [95% CI] | Break-even EUR/check [95% CI] |",
  "|---|---|---:|---:|---:|")
for (i in seq_len(nrow(contrasts))) {
  x <- contrasts[i, ]
  lines <- c(lines, sprintf("| %s | %s | %d | %+.2f [%+.2f, %+.2f] | %.4f [%.4f, %.4f] |",
    x$scenario, x$model, x$per_group, x$return_gain_eur_mean,
    x$return_gain_eur_lower_95, x$return_gain_eur_upper_95,
    x$break_even_eur_per_extra_inspection_mean,
    x$break_even_eur_per_extra_inspection_lower_95, x$break_even_eur_per_extra_inspection_upper_95))
}
ensemble <- subset(contrasts, model == "ensemble")
lines <- c(lines, "", "![Cost sensitivity of larger inspection plans](inspection_budget.png)", "",
  "## Interpretation and limits", "",
  sprintf("Larger plans improve mean ensemble Brier in %d of %d comparisons with the smallest plan.",
    sum(ensemble$brier_improvement_mean > 0), nrow(ensemble)),
  sprintf("Their mean sale-return gain is positive in %d of %d comparisons; at EUR 0.02/check,",
    sum(ensemble$return_gain_eur_mean > 0), nrow(ensemble)),
  sprintf("%d of %d mean gains remain positive after the extra inspection charges.",
    sum(ensemble$return_gain_eur_mean - 0.02 * ensemble$additional_inspections > 0), nrow(ensemble)),
  "A lower prediction error need not yield enough economic benefit to pay for more data.", "",
  "Thresholds concern these fixed policies and simulated lot distributions, not the",
  "optimal value of information or an empirically recommended budget. A negative",
  "threshold means the larger plan has a lower mean return even when checks are free.",
  "Intervals describe mean differences across simulated lots, not an individual lot's payoff.", "",
  "Inspection charges are incurred before the decision cutoff: they matter when",
  "planning a study, but are sunk and constant across sale dates within a chosen plan.",
  "The synthetic model assumes nondestructive inspections with no effect on fruit",
  "survival or inventory, independent binomial observations, known calibration and",
  "known future prices. Destructive sampling, handling damage and fixed visit costs",
  "are excluded. Calibration-reference and holdout evaluation costs are also excluded.", "",
  "Common inverse-CDF uniforms couple plans for Monte Carlo precision; larger plans",
  "are not constructed by adding observations to an actual smaller pilot sample.",
  "Each scenario has independent base lots; the paired scenarios/plans must not be",
  "pooled as independent replicates. Intervals have no multiplicity adjustment.",
  "No plan or model is selected using the reported future outcomes.", "",
  "```sh", sprintf("Rscript scripts/run_inspection_budget.R %d", n_lots), "```", "",
  "[Records](records.csv), [cost summaries](summary.csv), [paired contrasts](contrasts.csv)",
  "and [settings](settings.R) preserve all three models and all declared unit costs.",
  "See [INSPECTION_BUDGET.md](../../INSPECTION_BUDGET.md) for the estimands and protocol.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "inspection_budget.png"), width = 1800, height = 720, res = 140)
graphics::par(mfrow = c(1, 3), mar = c(5, 5.5, 5, 1), mgp = c(3.7, 1, 0))
costs <- seq(0, max(settings$costs_eur_per_inspection), length.out = 81)
limits <- range(c(0, ensemble$return_gain_eur_lower_95 - max(costs) * ensemble$additional_inspections,
                  ensemble$return_gain_eur_upper_95))
colours <- c("#276a98", "#bd6320")
titles <- c("Common shapes", "Nearby shapes", "Different shapes")
for (s in seq_len(nrow(settings$scenarios))) {
  part <- ensemble[ensemble$scenario == settings$scenarios$scenario[s], ]
  part <- part[order(part$per_group), ]
  graphics::plot(range(costs), limits, type = "n", las = 1,
    xlab = "EUR per inspected fruit", ylab = if (s == 1L) "Net gain over smallest plan (EUR per lot)" else "",
    main = titles[s])
  graphics::mtext("Ensemble; marginal 95% paired-lot intervals", side = 3, line = 0.5, cex = 0.7)
  graphics::abline(h = 0, col = "grey50", lty = 2)
  for (j in seq_len(nrow(part))) {
    charge <- costs * part$additional_inspections[j]
    lower <- part$return_gain_eur_lower_95[j] - charge
    upper <- part$return_gain_eur_upper_95[j] - charge
    graphics::polygon(c(costs, rev(costs)), c(lower, rev(upper)), border = NA,
      col = grDevices::adjustcolor(colours[j], alpha.f = 0.16))
    graphics::lines(costs, part$return_gain_eur_mean[j] - charge, col = colours[j], lwd = 2)
  }
  graphics::legend("bottomleft", sprintf("%d vs 30 per stratum/day", part$per_group),
    col = colours, lwd = 2, bty = "n", cex = 0.8)
}
invisible(grDevices::dev.off())
cat(sprintf("Wrote %d paired records to %s\n", nrow(records), destination))
