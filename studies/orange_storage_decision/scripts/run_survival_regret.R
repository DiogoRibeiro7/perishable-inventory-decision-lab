# Run from studies/orange_storage_decision:
# Rscript scripts/run_survival_regret.R [repetitions] [output_directory] [targets_per_repetition]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/robust_policy.R")
source("R/historical_baseline.R")
source("R/historical_evaluation.R")
source("R/archive_uncertainty.R")
source("R/historical_shift.R")
source("R/survival_regret.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 3L) stop("usage: run_survival_regret.R [repetitions] [output_directory] [targets_per_repetition]")
n_repeats <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 30L
destination <- if (length(args) >= 2L) args[2] else "results/survival_regret"
n_targets <- if (length(args) == 3L) suppressWarnings(as.numeric(args[3])) else 50L
settings <- list(n_repeats = n_repeats, n_targets = n_targets, n_history = 100L,
  decision_multipliers = c(0.75, 1, 1.25), evaluation_multipliers = c(0.6, 0.75, 1, 1.25, 1.4),
  master_seed = 20261119L, bootstrap_seed = 9219L, n_boot = 2000L,
  fit_calendar_day = 0L, target_harvest_day = 0L, historical_days = c(4L, 8L, 12L, 16L, 20L, 24L),
  historical_checks_per_group = 60L, sensitivity = 0.9, specificity = 0.9,
  decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
  storage_eur_per_kg_day = 0.001, fruit_mass_kg = 0.20,
  criterion = "minimum worst fitted regret over the finite decision multiplier set",
  resampling_unit = "independent historical archive plus paired target panel",
  r_version = R.version.string, rng_kind = RNGkind())
result <- run_survival_regret_experiment(n_repeats, n_targets, settings$n_history,
  settings$decision_multipliers, settings$evaluation_multipliers, settings$master_seed)
set.seed(settings$bootstrap_seed)
estimates <- summarize_survival_regret(result$records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
tables <- c(result, estimates)
for (name in names(tables)) utils::write.csv(tables[[name]], file.path(destination, paste0(name, ".csv")), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"), file.path(destination, "settings.R"), useBytes = TRUE)

interval <- function(factor, metric, percentage = FALSE) {
  x <- estimates$summary[estimates$summary$lifetime_multiplier == factor & estimates$summary$metric == metric, ]
  scale <- if (percentage) 100 else 1
  sprintf("%.2f [%.2f, %.2f]", scale * x$mean, scale * x$lower_95, scale * x$upper_95)
}
decisions <- result$records[result$records$lifetime_multiplier == 1, ]
lines <- c("# Minimax regret for uncertain target shelf life", "",
  sprintf("%d independent repetitions, each with %d historical lots and %d fresh target lots.",
    n_repeats, settings$n_history, n_targets),
  "The historical rule optimises its fitted survival curves. The robust rule",
  "minimises worst fitted regret over lifetime multipliers 0.75, 1 and 1.25.",
  "Regret is the loss relative to the best fitted date within each scenario.",
  "Both rules use the same frozen model, initial masses and supplied price path.",
  "All dates precede target fruit outcomes; neither rule knows the realised shift.", "",
  sprintf("There are %d unique target lots and %d paired target/scenario records.",
    n_repeats * n_targets, nrow(result$records)),
  "Multipliers 0.60 and 1.40 lie outside the decision set. Evaluation scenarios",
  "share each target's fruit identities, masses and prices. Scenarios have no",
  "assigned probabilities and are not averaged into an overall performance score.", "",
  "## Paired deployment returns", "",
  "EUR per target lot, mean [marginal 95% percentile interval]. Intervals resample",
  "whole independent train/test repetitions and preserve all policy/scenario pairs.", "",
  "| Target lifetime factor | In decision set? | Robust minus historical | Historical minus day 12 | Robust minus day 12 |",
  "|---|---|---:|---:|---:|")
for (factor in settings$evaluation_multipliers) {
  lines <- c(lines, sprintf("| %.2f | %s | %s | %s | %s |", factor,
    if (factor %in% settings$decision_multipliers) "Yes" else "No",
    interval(factor, "robust_minus_nominal_eur"), interval(factor, "nominal_minus_day12_eur"),
    interval(factor, "robust_minus_day12_eur")))
}
lines <- c(lines, "", "## Strict-loss frequencies", "",
  "Percent of target lots, mean [95% interval]. Ties are not losses.", "",
  "| Target lifetime factor | Robust below historical (%) | Historical below day 12 (%) | Robust below day 12 (%) |",
  "|---|---:|---:|---:|")
for (factor in settings$evaluation_multipliers) {
  lines <- c(lines, sprintf("| %.2f | %s | %s | %s |", factor,
    interval(factor, "robust_below_nominal", TRUE), interval(factor, "nominal_below_day12", TRUE),
    interval(factor, "robust_below_day12", TRUE)))
}
lines <- c(lines, "", "## Fitted decision diagnostics", "",
  sprintf("Mean sale day: historical %.2f, robust %.2f; dates differ on %.1f%% of target lots.",
    mean(decisions$nominal_day), mean(decisions$robust_day), 100 * mean(decisions$nominal_day != decisions$robust_day)),
  sprintf("Mean worst fitted regret across the decision set: historical EUR %.2f, robust EUR %.2f.",
    mean(decisions$fitted_nominal_worst_regret_eur), mean(decisions$fitted_robust_worst_regret_eur)),
  "The robust date cannot have larger worst fitted regret than another candidate",
  "date in its own model. That optimisation property is not an empirical return",
  "guarantee. The model is a working marginal Weibull fit, rather than the true",
  "survival curve of a particular target lot.", "",
  "![Survival-regret policy comparison](survival_regret.png)", "",
  "## Interpretation limits", "",
  "Robust means minimax regret over a finite, declared model set. It does not",
  "mean best realised return, smallest worst loss, a calibrated survival forecast",
  "or a bound for every multiplier between the three decision values. The",
  "outside-set scenarios test sensitivity beyond those assumptions. Outcomes",
  "must be considered separately by scenario, including any losses in unchanged",
  "or longer-lived populations. No policy or scenario set was tuned on these targets.", "",
  "Every policy retains 850 kg of initially eligible fruit, with no target",
  "inspection. Realised returns include holding from harvest through delivery",
  "at EUR 0.001/kg/day and a two-day lag. Fitted decisions use future costs from",
  "day 12; the common sunk holding cost cancels from fitted regret. Initially",
  "immature fruit remain excluded. Archive acquisition, destructive sampling,",
  "labour and development costs are not included.", "",
  "History has six ages and 60 checks per stratum/age/lot, with known grading",
  "sensitivity/specificity of 0.90. Initial grades and prices are assumed known.",
  "Shifts multiply target lifetimes from harvest, equally across both eligible",
  "strata, preserving Weibull shapes. Shared latent fruit ranks couple scenarios.",
  "This remains synthetic evidence without field validation or shift probabilities.", "",
  "The independent sample size is the repetition count. The 2,000 bootstrap",
  "resamples include archive and finite-test-panel variation, using common",
  "repetition indices across metrics and scenarios. Intervals concern expected",
  "performance, are marginal without multiplicity adjustment, and do not predict",
  "the next lot's return. Failed repetitions stop the study rather than being dropped.", "",
  "## Reproduction", "", "```sh",
  sprintf("Rscript scripts/run_survival_regret.R %d results/survival_regret %d", n_repeats, n_targets), "```", "",
  "[Seeds](seeds.csv), [aggregate training counts](counts.csv), [fitted curves](fits.csv),",
  "[paired target records](records.csv), [repetition means](repetitions.csv),",
  "[intervals](summary.csv) and [settings](settings.R) preserve the calculations.",
  "The seed manifest regenerates individual historical lots and target panels.",
  "See [SURVIVAL_REGRET.md](../../SURVIVAL_REGRET.md) for the protocol and API.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "survival_regret.png"), width = 1500, height = 820, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 5, 4, 1), mgp = c(3.4, 1, 0))
nominal <- estimates$summary[estimates$summary$metric == "nominal_minus_day12_eur", ]
robust <- estimates$summary[estimates$summary$metric == "robust_minus_day12_eur", ]
graphics::plot(NA, xlim = c(0.53, 1.47), ylim = range(c(0, nominal$lower_95, nominal$upper_95, robust$lower_95, robust$upper_95)),
  xlab = "Target lifetime multiplier", ylab = "Mean advantage over day-12 sale (EUR/lot)",
  main = "Deployment tradeoffs", xaxt = "n", las = 1)
graphics::axis(1, at = settings$evaluation_multipliers)
graphics::abline(h = 0, lty = 2, col = "grey50")
for (j in 1:2) {
  x <- if (j == 1) nominal else robust
  colour <- c("#b25a2b", "#276a98")[j]
  position <- x$lifetime_multiplier + c(-0.012, 0.012)[j]
  graphics::arrows(position, x$lower_95, position, x$upper_95, code = 3, angle = 90, length = 0.05, col = colour)
  graphics::points(position, x$mean, pch = c(17, 19)[j], col = colour)
}
graphics::legend("topleft", legend = c("Historical", "Minimax regret"), pch = c(17, 19), col = c("#b25a2b", "#276a98"), bty = "n", cex = 0.8)
x <- estimates$summary[estimates$summary$metric == "robust_minus_nominal_eur", ]
graphics::plot(x$lifetime_multiplier, x$mean, xlim = c(0.53, 1.47),
  ylim = range(c(0, x$lower_95, x$upper_95)), pch = 19, col = "#276a98", xaxt = "n", las = 1,
  xlab = "Target lifetime multiplier", ylab = "Mean robust minus historical return (EUR/lot)", main = "Paired policy difference")
graphics::axis(1, at = settings$evaluation_multipliers)
graphics::abline(h = 0, lty = 2, col = "grey50")
graphics::arrows(x$lifetime_multiplier, x$lower_95, x$lifetime_multiplier, x$upper_95,
  code = 3, angle = 90, length = 0.05, col = "#276a98")
for (side in 1:2) {
  graphics::mtext("95% repetition intervals; 0.60 and 1.40 outside decision set", side = 3, line = 0.4, cex = 0.7, at = NA)
  if (side == 1) graphics::par(mfg = c(1, 1))
}
invisible(grDevices::dev.off())
cat(sprintf("Wrote %d survival-regret repetitions to %s\n", n_repeats, destination))
