# Run from studies/orange_storage_decision:
# Rscript scripts/run_historical_shift.R [repetitions] [output_directory] [targets_per_repetition]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")
source("R/historical_shift.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 3L) stop("usage: run_historical_shift.R [repetitions] [output_directory] [targets_per_repetition]")
n_repeats <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 30L
destination <- if (length(args) >= 2L) args[2] else "results/historical_shift"
n_targets <- if (length(args) == 3L) suppressWarnings(as.numeric(args[3])) else 50L
settings <- list(n_repeats = n_repeats, n_targets = n_targets, n_history = 100L,
  lifetime_multipliers = c(0.75, 1, 1.25), master_seed = 20261118L,
  bootstrap_seed = 9218L, n_boot = 2000L, fit_calendar_day = 0L, target_harvest_day = 0L,
  historical_days = c(4L, 8L, 12L, 16L, 20L, 24L), historical_checks_per_group = 60L,
  sensitivity = 0.9, specificity = 0.9, decision_day = 12L, last_sale_day = 28L,
  forecast_days = c(16L, 20L, 24L), delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, fruit_mass_kg = 0.20,
  shift_onset = "target harvest; historical generating regime unchanged",
  resampling_unit = "independent training archive plus paired target scenarios",
  r_version = R.version.string, rng_kind = RNGkind())
result <- run_historical_shift_experiment(n_repeats, n_targets, settings$n_history,
  settings$lifetime_multipliers, settings$master_seed)
set.seed(settings$bootstrap_seed)
estimates <- summarize_historical_shift(result$records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
tables <- c(result, estimates)
for (name in names(tables)) utils::write.csv(tables[[name]], file.path(destination, paste0(name, ".csv")), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"), file.path(destination, "settings.R"), useBytes = TRUE)

labels <- c(return_eur = "Return (EUR/lot)", gain_day12_eur = "Gain vs day 12 (EUR/lot)",
  gain_day16_eur = "Gain vs day 16 (EUR/lot)", below_day12 = "Below day 12 (%)",
  brier = "Brier score", log_loss = "Log loss", bias_day16_kg = "Day 16 inventory bias (kg)",
  bias_day20_kg = "Day 20 inventory bias (kg)", bias_day24_kg = "Day 24 inventory bias (kg)")
format_interval <- function(x) {
  digits <- if (x$metric %in% c("brier", "log_loss")) 5L else 2L
  scale <- if (x$metric == "below_day12") 100 else 1
  sprintf("%.*f [%.*f, %.*f]", digits, scale * x$mean, digits, scale * x$lower_95, digits, scale * x$upper_95)
}
lines <- c("# A frozen historical model under shelf-life shift", "",
  sprintf("%d independent train/test repetitions; %d historical and %d fresh target lots per repetition.",
    n_repeats, settings$n_history, n_targets),
  "Each target's fruit lifetimes are multiplied by 0.75, 1 or 1.25 from harvest:",
  "25% shorter, unchanged or 25% longer shelf life. Historical data stay unchanged.",
  "Both initially eligible strata share the multiplier; Weibull shapes stay fixed.",
  "These are declared stress scenarios, not estimated probabilities of future shifts.", "",
  sprintf("The %d unique target lots produce %d paired target/scenario records.", n_repeats * n_targets, nrow(result$records)),
  "The model, all sale dates and all predicted masses are frozen before target",
  "fruit outcomes. The policy receives no shift indicator or target inspection.", "",
  "## Expected deployment performance", "",
  "Values are means with marginal 95% percentile intervals. Entire independent",
  "train/test repetitions are resampled, keeping all target scenarios paired.",
  "Intervals include training-archive and finite-target-panel variation; they",
  "concern expected performance, not the outcome range of an individual lot.", "",
  "| Metric | 25% shorter | Unchanged | 25% longer |", "|---|---:|---:|---:|")
for (metric in names(labels)) {
  cells <- vapply(settings$lifetime_multipliers, function(factor) {
    format_interval(estimates$summary[estimates$summary$metric == metric & estimates$summary$lifetime_multiplier == factor, ])
  }, character(1))
  lines <- c(lines, paste0("| ", labels[metric], " | ", paste(cells, collapse = " | "), " |"))
}
lines <- c(lines, "", "## Paired change relative to the unchanged scenario", "",
  "Each contrast is shifted minus unchanged, computed within a repetition.",
  "Fixed-date returns also change with shelf life: a change in policy advantage",
  "is distinct from a change in the policy's absolute return. Downside contrasts",
  "are percentage-point changes. Signed bias changes are not improvements by",
  "themselves; zero absolute bias is ideal.", "",
  "| Metric | 25% shorter minus unchanged | 25% longer minus unchanged |", "|---|---:|---:|")
for (metric in names(labels)) {
  cells <- vapply(c(0.75, 1.25), function(factor) {
    format_interval(estimates$contrasts[estimates$contrasts$metric == metric & estimates$contrasts$lifetime_multiplier == factor, ])
  }, character(1))
  lines <- c(lines, paste0("| ", labels[metric], " | ", paste(cells, collapse = " | "), " |"))
}
lines <- c(lines, "", "![Returns and inventory bias under shelf-life shift](historical_shift.png)", "",
  "## What the stress test establishes", "",
  "This isolates an unobserved target shift from harvest, with historical curves",
  "held fixed. It does not evaluate shift detection, retraining, adaptation or an",
  "oracle policy that knows the multiplier. Fruit identity, initial masses and",
  "prices are shared across scenarios; all comparators face the same shifted fruit.",
  "A constant lifetime multiplier is not a constant hazard multiplier when",
  "strata have different Weibull shapes, and this is not a post-decision shock.", "",
  "Brier/log loss assess true individual-fruit acceptance and are weighted by",
  "initial stratum mass, then averaged equally over days 16/20/24 and target lots.",
  "Score changes across scenarios also reflect changing acceptance prevalence",
  "and outcome uncertainty; they alone do not isolate calibration deterioration.",
  "Inventory bias is predicted minus observed acceptable mass. Positive bias",
  "means overprediction; repeated future measurements stay within each repetition.", "",
  "All policies retain 850 kg of initially eligible fruit. Returns include",
  "holding from harvest through delivery at EUR 0.001/kg/day and a two-day lag.",
  "Known supplied prices and grading sensitivity/specificity of 0.90 are assumed.",
  "Each historical archive contains 72,000 reported checks. Archive collection,",
  "destructive losses, labour and development costs are excluded. Initially",
  "immature fruit remain outside sale revenue and eligible holding costs.", "",
  "The shifts, model and evaluation settings were fixed before target scoring.",
  "There is no shift-probability model or empirical field validation. The 2,000",
  "bootstrap draws resample whole independent repetitions with common indices",
  "across metrics/scenarios. Intervals are marginal, without multiplicity",
  "adjustment; thousands of target/scenario rows do not create extra independent",
  "training archives. Fit failures stop the study instead of dropping repetitions.", "",
  "## Reproduction", "", "```sh",
  sprintf("Rscript scripts/run_historical_shift.R %d results/historical_shift %d", n_repeats, n_targets), "```", "",
  "[Seeds](seeds.csv) regenerate the historical archives and coupled target panels.",
  "[Training counts](counts.csv), [fits](fits.csv), [target records](records.csv),",
  "[repetition means](repetitions.csv), [performance intervals](summary.csv),",
  "[paired contrasts](contrasts.csv) and [settings](settings.R) preserve the evidence.",
  "Training counts are aggregated; the seed manifest preserves individual-lot",
  "provenance. See [HISTORICAL_SHIFT.md](../../HISTORICAL_SHIFT.md) for the protocol.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "historical_shift.png"), width = 1500, height = 820, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 5, 4, 1), mgp = c(3.4, 1, 0))
panels <- list(list(metric = "gain_day12_eur", title = "Advantage over fixed sale on day 12",
    ylab = "Mean return advantage per target lot (EUR)"),
  list(metric = "bias_day20_kg", title = "Inventory forecast bias at day 20",
    ylab = "Mean predicted minus observed acceptable kg"))
for (panel in panels) {
  x <- estimates$summary[estimates$summary$metric == panel$metric, ]
  graphics::plot(x$lifetime_multiplier, x$mean, pch = 19, col = "#276a98", xaxt = "n", las = 1,
    ylim = range(c(0, x$lower_95, x$upper_95)), xlim = c(0.68, 1.32),
    xlab = "Target fruit lifetime multiplier", ylab = panel$ylab, main = panel$title)
  graphics::mtext("95% intervals across independent train/test repetitions", side = 3, line = 0.4, cex = 0.7)
  graphics::axis(1, at = x$lifetime_multiplier, labels = c("0.75\nShorter", "1.00\nUnchanged", "1.25\nLonger"))
  graphics::abline(h = 0, lty = 2, col = "grey50")
  graphics::arrows(x$lifetime_multiplier, x$lower_95, x$lifetime_multiplier, x$upper_95,
    code = 3, angle = 90, length = 0.06, col = "#276a98", lwd = 2)
}
invisible(grDevices::dev.off())
cat(sprintf("Wrote %d paired shelf-life-shift repetitions to %s\n", n_repeats, destination))
