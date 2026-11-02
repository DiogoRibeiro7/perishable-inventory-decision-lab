# Run from studies/orange_storage_decision:
# Rscript scripts/run_survival_stress.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/price_sensitivity.R")
source("R/robust_policy.R")
source("R/survival_stress.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) {
  stop("usage: Rscript scripts/run_survival_stress.R [number_of_lots] [output_directory]",
       call. = FALSE)
}
n_lots <- if (length(args) >= 1L) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) >= 2L) args[2] else "results/survival_stress"
settings <- list(n_lots = n_lots, simulation_seed = 20261026L,
                 inspection_seed = 20261027L, bootstrap_seed = 9189L, n_boot = 1000L,
                 decision_day = 12L, change_day = 12L, delivery_lag_days = 2L,
                 holdout_days = c(16L, 20L, 24L), holdout_per_group = 250L,
                 storage_eur_per_kg_day = 0.001, price_decision_ratios = c(0.6, 0.8, 1),
                 scenarios = default_survival_scenarios(),
                 r_version = R.version.string, rng_kind = RNGkind())
records <- run_survival_stress(n_lots, settings$simulation_seed,
                               settings$inspection_seed, settings$scenarios)
set.seed(settings$bootstrap_seed)
summary <- summarize_survival_stress(records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"),
            file.path(destination, "settings.R"), useBytes = TRUE)

lines <- c(
  "# Deterioration after the decision cutoff: synthetic results", "",
  sprintf("%d independent lots; policies fitted and fixed before the day-12 hazard change.", n_lots),
  "Every scenario shares training inspections, sale dates, fruit identities and",
  "future inspection uniforms. Realised prices equal the original forecast.",
  "Immediate sale still faces deterioration before acceptance on day 14.", "",
  "## Out-of-time prediction errors", "",
  "Bias is predicted minus observed acceptable fraction, in percentage points,",
  "standardised by inventory mass and averaged over future days and lots.",
  "Positive bias means overprediction. Brier and log loss are individual-fruit",
  "proper scores (lower is better); their levels also depend on prevalence.", "",
  "| Scenario | Post-cutoff hazard factor | Stratified bias, pp [95% CI] | Pooled bias, pp | Stratified Brier | Pooled Brier | Stratified log loss | Pooled log loss |",
  "|---|---:|---:|---:|---:|---:|---:|---:|"
)
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf(
    "| %s | %.1f | %+.2f [%+.2f, %+.2f] | %+.2f | %.4f | %.4f | %.4f | %.4f |",
    x$scenario, x$hazard_multiplier, 100 * x$mean_bias_stratified,
    100 * x$bias_stratified_lower_95, 100 * x$bias_stratified_upper_95,
    100 * x$mean_bias_pooled, x$mean_brier_stratified, x$mean_brier_pooled,
    x$mean_log_loss_stratified, x$mean_log_loss_pooled))
}
lines <- c(lines, "", "## Mean realised net return per initially eligible 850-kg lot", "",
  "All returns are EUR after storage and delivery rejection.", "",
  "| Scenario | Stratified | Pooled | Price minimax | Immediate |",
  "|---|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.2f | %.2f | %.2f | %.2f |", x$scenario,
    x$mean_stratified_eur, x$mean_pooled_eur, x$mean_robust_eur, x$mean_immediate_eur))
}
lines <- c(lines, "", "## Paired differences against immediate sale", "",
  "Mean differences have marginal 95% whole-lot bootstrap intervals.",
  "Underperformance fractions are descriptive and exclude exact ties.", "",
  "| Scenario | Stratified - immediate, EUR [95% CI] | Price minimax - immediate, EUR [95% CI] | Stratified below immediate | Price minimax below immediate |",
  "|---|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf(
    "| %s | %+.2f [%+.2f, %+.2f] | %+.2f [%+.2f, %+.2f] | %.1f%% | %.1f%% |",
    x$scenario, x$stratified_minus_immediate_mean_eur,
    x$stratified_minus_immediate_lower_95_eur, x$stratified_minus_immediate_upper_95_eur,
    x$robust_minus_immediate_mean_eur, x$robust_minus_immediate_lower_95_eur,
    x$robust_minus_immediate_upper_95_eur, 100 * x$stratified_below_immediate_fraction,
    100 * x$robust_below_immediate_fraction))
}
lines <- c(lines, "", "![Calibration and policy returns](survival_stress.png)", "",
  "## Interpretation and reproduction", "",
  "Hazard factors are sensitivity assumptions, not estimates from storage data.",
  "The price-minimax rule considers a finite set of fitted mean-price scenarios;",
  "it does not model this deterioration shift. No policy observes or adapts to it.",
  "Reported intervals describe simulation uncertainty and are not adjusted for",
  "multiple comparisons. Aggregate bias can conceal errors within grades/days;",
  "cross-scenario proper-score changes also reflect changed outcome prevalence.",
  "The unchanged scenario preserves baseline economic outcomes; holdout quality",
  "counts are newly drawn with a separate seed and coupled across hazard settings.", "",
  "From the project folder:", "", "```sh",
  sprintf("Rscript scripts/run_survival_stress.R %d", n_lots), "```", "",
  "[records.csv](records.csv), [summary.csv](summary.csv), and [settings.R](settings.R)",
  "contain paired lot measurements, all statistics (including pooled contrasts",
  "and downside percentiles), and reproduction settings.",
  "See [SURVIVAL_STRESS.md](../../SURVIVAL_STRESS.md) for the generator and limits.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "survival_stress.png"), width = 1600, height = 800, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(4.5, 4.5, 4, 1))
ordered <- summary[order(summary$hazard_multiplier), ]
x <- ordered$hazard_multiplier
lower <- 100 * ordered$bias_stratified_lower_95
upper <- 100 * ordered$bias_stratified_upper_95
graphics::plot(x, 100 * ordered$mean_bias_stratified, type = "b", pch = 19,
                 ylim = range(c(0, lower, upper)), xaxt = "n", las = 1,
                 xlab = "Hazard multiplier after day 12", ylab = "Predicted minus observed (pp)",
                 main = "Stratified survival calibration", col = "#276a98")
graphics::axis(1, x, x)
graphics::mtext("95% whole-lot bootstrap intervals", side = 3, line = 0.4, cex = 0.75)
graphics::abline(h = 0, col = "grey50", lty = 2)
graphics::arrows(x, lower, x, upper, angle = 90, code = 3, length = 0.05, col = "#276a98")
bounds <- unlist(ordered[c("stratified_minus_immediate_lower_95_eur",
                           "stratified_minus_immediate_upper_95_eur",
                           "robust_minus_immediate_lower_95_eur",
                           "robust_minus_immediate_upper_95_eur")])
graphics::plot(x, ordered$stratified_minus_immediate_mean_eur, type = "n",
                 ylim = range(c(0, bounds)), xaxt = "n", las = 1,
                 xlab = "Hazard multiplier after day 12", ylab = "Mean paired difference (EUR per lot)",
                 main = "Returns relative to immediate sale")
graphics::axis(1, x, x)
graphics::mtext("95% paired lot-bootstrap intervals", side = 3, line = 0.4, cex = 0.75)
graphics::abline(h = 0, col = "grey50", lty = 2)
policies <- c("stratified", "robust")
for (i in seq_along(policies)) {
  prefix <- paste0(policies[i], "_minus_immediate_")
  colour <- c("#276a98", "#b85a18")[i]
  offset <- c(-0.015, 0.015)[i]
  graphics::lines(x + offset, ordered[[paste0(prefix, "mean_eur")]], type = "b",
                   pch = c(19, 17)[i], col = colour)
  graphics::arrows(x + offset, ordered[[paste0(prefix, "lower_95_eur")]],
                    x + offset, ordered[[paste0(prefix, "upper_95_eur")]],
                    angle = 90, code = 3, length = 0.04, col = colour)
}
graphics::legend("topright", c("Stratified", "Price minimax"),
                   col = c("#276a98", "#b85a18"), pch = c(19, 17), lty = 1, bty = "n", cex = 0.85)
invisible(grDevices::dev.off())
print(summary, row.names = FALSE)
cat(sprintf("\nWrote %d paired records to %s\n", nrow(records), destination))
