# Run from studies/orange_storage_decision:
# Rscript scripts/run_inspection_removals.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shared_shape_evaluation.R")
source("R/shape_ensemble.R")
source("R/inspection_removals.R")
source("R/removal_evaluation.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) stop("usage: run_inspection_removals.R [number_of_lots] [output_directory]")
n_lots <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) == 2L) args[2] else "results/inspection_removals"
settings <- list(n_lots = n_lots, training_seed = 20261108L, outcome_seed = 20261109L,
  bootstrap_seed = 9214L, n_boot = 1000L, training_per_group = 180L,
  training_days = c(3L, 6L, 9L, 12L), fruit_mass_kg = 0.20,
  inspection_eur_per_fruit = 0.02, sensitivity = 0.9, specificity = 0.9,
  decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, r_version = R.version.string, rng_kind = RNGkind())
records <- run_removal_experiment(n_lots, settings$training_seed, settings$outcome_seed)
set.seed(settings$bootstrap_seed)
summary <- summarize_removal_experiment(records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"),
  file.path(destination, "settings.R"), useBytes = TRUE)

x <- summary[1, ]
lines <- c("# Destructive inspections: valuing the fruit that remains", "",
  sprintf("%d fresh independent synthetic lots; one fixed inspection plan and identical survival fits for both decisions.", n_lots),
  "Each lot starts with 850 kg of eligible fruit. Inspecting and removing 180 fruit",
  "per stratum on four days removes 1,440 fruit at 0.20 kg each: 288 kg in total.",
  "The day-12 remaining eligible inventory is 562 kg. No removed fruit can be sold.", "",
  "The inventory-unaware rule chooses a date using the original masses. The",
  "removal-aware rule uses the observed ledger and charges future holding costs",
  "only on remaining mass. Both use the same fitted AIC-weighted survival mixture.",
  "All decisions are fixed before generating the remaining fruit's outcomes.", "",
  "## Forecast accounting versus decision benefit", "",
  "The first contrast holds the old sale date and fitted curves fixed, changing only",
  "the inventory ledger. The second reoptimises the date on the corrected fitted curve.",
  "Neither contrast is itself a realised profit improvement.", "",
  "| Contrast | Mean EUR per lot [95% paired-lot CI] |", "|---|---:|",
  sprintf("| Original-mass minus remaining-mass fitted value at the old date | %+.2f [%+.2f, %+.2f] |",
    x$fitted_value_difference_eur_mean, x$fitted_value_difference_eur_lower_95, x$fitted_value_difference_eur_upper_95),
  sprintf("| Fitted gain from reoptimising after removals | %+.2f [%+.2f, %+.2f] |",
    x$fitted_decision_gain_eur_mean, x$fitted_decision_gain_eur_lower_95, x$fitted_decision_gain_eur_upper_95),
  sprintf("| True expected gain from the changed date | %+.2f [%+.2f, %+.2f] |",
    x$expected_return_gain_eur_mean, x$expected_return_gain_eur_lower_95, x$expected_return_gain_eur_upper_95),
  sprintf("| Realised removal-aware minus inventory-unaware return | %+.2f [%+.2f, %+.2f] |",
    x$realised_return_gain_eur_mean, x$realised_return_gain_eur_lower_95, x$realised_return_gain_eur_upper_95), "",
  "True expected values use inaccessible generating survival curves on the actual",
  "remaining inventory, only for evaluation. Policies never receive those parameters.", "",
  "## Actual remaining-inventory returns", "",
  "All returns include delivery rejection, post-cutoff holding cost and EUR 28.80",
  "of already-incurred inspection labour (hypothetical EUR 0.02 per check).",
  "Immediate sale also follows the same completed destructive inspections.", "",
  "| Policy | Mean sale day | Mean realised EUR | Below immediate sale |",
  "|---|---:|---:|---:|",
  sprintf("| Inventory-unaware | %.2f | %.2f | %.1f%% |", x$mean_sale_day_naive,
    x$mean_realised_naive_eur, 100 * x$naive_below_immediate_fraction),
  sprintf("| Removal-aware | %.2f | %.2f | %.1f%% |", x$mean_sale_day_accounted,
    x$mean_realised_accounted_eur, 100 * x$accounted_below_immediate_fraction),
  sprintf("| Immediate after inspection | 12.00 | %.2f | -- |", x$mean_realised_immediate_eur), "",
  sprintf("Accounting for removals changes %.1f%% of sale dates; the corrected decision earns less than the unaware decision on %.1f%% of lots.",
    100 * x$different_sale_day_fraction, 100 * x$accounted_below_naive_fraction),
  sprintf("Its mean realised advantage over immediate sale is EUR %+.2f [%.2f, %.2f].",
    x$accounted_minus_immediate_eur_mean, x$accounted_minus_immediate_eur_lower_95,
    x$accounted_minus_immediate_eur_upper_95), "",
  "![Accounting and decision contrasts](inspection_removals.png)", "",
  "## Interpretation and reproduction", "",
  "A corrected inventory value is not an equal-sized profit gain. Decisions can",
  "remain unchanged, and fitting error can make a revised date worse on some lots.",
  "This study isolates decisions after a fixed inspection plan. It does not compare",
  "destructive versus nondestructive plans or establish the value of inspections.", "",
  "Removed samples are random within each initial stratum, independent of fruit",
  "survival and mass. Remaining fruit can already be unacceptable; this is not",
  "selective culling or conditioning survival on passing a day-12 inspection.",
  "No inspection damage to the remainder, disposal revenue/cost, calibration",
  "uncertainty, shared storage shocks or price errors are modeled. Marginal",
  "bootstrap intervals are not adjusted for multiple contrasts; downside fractions",
  "use all lots as the denominator and count strictly lower returns. Synthetic",
  "results are not evidence of field profitability.", "",
  "```sh", sprintf("Rscript scripts/run_inspection_removals.R %d", n_lots), "```", "",
  "[Records](records.csv), [summary](summary.csv) and [settings](settings.R) preserve the results.",
  "See [INSPECTION_REMOVALS.md](../../INSPECTION_REMOVALS.md) for the ledger contract and protocol.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "inspection_removals.png"), width = 1500, height = 780, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 5, 4, 1), mgp = c(3.5, 1, 0))
fields <- c("fitted_value_difference_eur", "realised_return_gain_eur")
for (i in seq_along(fields)) {
  field <- fields[i]
  mean <- x[[paste0(field, "_mean")]]
  lower <- x[[paste0(field, "_lower_95")]]
  upper <- x[[paste0(field, "_upper_95")]]
  graphics::plot(1, mean, xlim = c(0.5, 1.5), ylim = range(c(0, lower, upper)),
    pch = 19, col = "#276a98", xaxt = "n", las = 1, xlab = "", ylab = "Mean EUR per lot",
    main = c("Fitted inventory-value difference", "Realised decision benefit")[i])
  graphics::mtext("95% paired whole-lot bootstrap interval", side = 3, line = 0.4, cex = 0.75)
  graphics::abline(h = 0, col = "grey50", lty = 2)
  if (upper > lower) graphics::arrows(1, lower, 1, upper, code = 3, angle = 90, length = 0.08, col = "#276a98")
  graphics::axis(1, at = 1, labels = c("Original minus remaining mass\nat the old selected date",
    "Removal-aware minus unaware\non the same remaining fruit")[i], cex.axis = 0.85)
}
invisible(grDevices::dev.off())
cat(sprintf("Wrote %d paired records to %s\n", nrow(records), destination))
