# Run from studies/orange_storage_decision:
# Rscript scripts/run_price_sensitivity.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/price_sensitivity.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) {
  stop("usage: Rscript scripts/run_price_sensitivity.R [number_of_lots] [output_directory]",
       call. = FALSE)
}
n_lots <- if (length(args) >= 1L) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) >= 2L) args[2] else "results/price_sensitivity"
settings <- list(n_lots = n_lots, simulation_seed = 20261022L,
                 price_seed = 20261023L, bootstrap_seed = 9187L, n_boot = 1000L,
                 decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
                 scenarios = default_price_scenarios(),
                 r_version = R.version.string, rng_kind = RNGkind())
records <- run_price_sensitivity(n_lots, settings$simulation_seed,
                                 settings$price_seed, settings$scenarios)
set.seed(settings$bootstrap_seed)
summary <- summarize_price_sensitivity(records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
settings_text <- trimws(capture.output(dput(settings)), which = "right")
writeLines(settings_text, file.path(destination, "settings.R"), useBytes = TRUE)

lines <- c(
  "# Price forecast sensitivity: synthetic results", "",
  sprintf("%d independent lots; decisions fixed at day 12 from forecast prices.", n_lots),
  "All scenarios share lots, fruit lifetimes and forecast-based sale dates.",
  "Price multipliers are shared across grades; the day-12 price is known.",
  "The perfect-forecast row uses the original evaluation's seeded lots.", "",
  "## Realised net return per initially eligible 850-kg lot", "",
  "All values are EUR. Intervals resample paired lots and describe uncertainty",
  "in mean policy contrasts under this synthetic generator, not field validity.", "",
  "| Price scenario | Stratified | Pooled | Immediate | Stratified - pooled [95% CI] | Stratified - immediate [95% CI] |",
  "|---|---:|---:|---:|---:|---:|"
)
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf(
    "| %s | %.2f | %.2f | %.2f | %+.2f [%+.2f, %+.2f] | %+.2f [%+.2f, %+.2f] |",
    x$scenario, x$mean_stratified_eur, x$mean_pooled_eur, x$mean_immediate_eur,
    x$stratified_minus_pooled_eur, x$pooled_contrast_lower_95, x$pooled_contrast_upper_95,
    x$stratified_minus_immediate_eur, x$immediate_contrast_lower_95,
    x$immediate_contrast_upper_95
  ))
}
lines <- c(lines, "", "## Downside and price-error impact", "",
  "Fractions and 10th percentiles are descriptive sample summaries. Exact ties",
  "are not counted as underperformance. Price impact compares the same policy",
  "on the same lot with its perfect-forecast realised return.", "",
  "| Scenario | Stratified below immediate | Pooled below immediate | 10th percentile: stratified - immediate, EUR | Mean price impact on stratified, EUR |",
  "|---|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.1f%% | %.1f%% | %+.2f | %+.2f |",
    x$scenario, 100 * x$stratified_below_immediate_fraction,
    100 * x$pooled_below_immediate_fraction,
    x$stratified_minus_immediate_p10_eur, x$mean_price_impact_stratified_eur))
}
lines <- c(lines, "", "![Paired profit differences](price_sensitivity.png)", "",
  "## Interpretation and reproduction", "",
  "Unbiased noise changes dispersion without changing conditional mean prices.",
  "The lower-mean scenarios gradually lower expected realised prices to 80% or",
  "60% of forecast at day 28, with terminal log-error SD 0.2. These settings",
  "are sensitivity assumptions, not estimates of orange-market forecast errors.",
  "The policies are not adapted or chosen using these results. No oracle is",
  "reported: the original forecast-informed oracle need not be optimal under",
  "a biased realised price process. Shared grade shocks, independent lots and",
  "Weibull deterioration remain restrictive assumptions.", "",
  "From the project folder:", "", "```sh",
  sprintf("Rscript scripts/run_price_sensitivity.R %d", n_lots), "```", "",
  "[records.csv](records.csv) contains paired lot/scenario measurements;",
  "[summary.csv](summary.csv) contains all contrasts and descriptive risks;",
  "[settings.R](settings.R) records seeds, scenarios, bootstrap count and R version.",
  "See [the study design](../../PRICE_SENSITIVITY.md) for the price process and limitations.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "price_sensitivity.png"),
                width = 1440, height = 760, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(4.5, 4.5, 4, 1))
labels <- c(perfect_forecast = "Perfect\nforecast", unbiased_noise = "Unbiased\nnoise",
            mean_20pct_lower = "Mean 20%\nlower", mean_40pct_lower = "Mean 40%\nlower")
for (contrast in c("pooled", "immediate")) {
  mean <- summary[[paste0("stratified_minus_", contrast, "_eur")]]
  lower <- summary[[paste0(contrast, "_contrast_lower_95")]]
  upper <- summary[[paste0(contrast, "_contrast_upper_95")]]
  graphics::plot(seq_len(nrow(summary)), mean, ylim = range(c(lower, upper, 0)),
                 xaxt = "n", xlab = "", ylab = "Mean paired difference (EUR per lot)",
                 main = paste("Stratified minus", contrast), pch = 19, col = "#276a98", las = 1)
  graphics::mtext("95% paired lot-bootstrap intervals", side = 3, line = 0.4, cex = 0.75)
  graphics::abline(h = 0, col = "grey50", lty = 2)
  graphics::arrows(seq_len(nrow(summary)), lower, seq_len(nrow(summary)), upper,
                   angle = 90, code = 3, length = 0.06, col = "#276a98")
  graphics::axis(1, seq_len(nrow(summary)), labels[summary$scenario], las = 1, cex.axis = 0.8)
}
invisible(grDevices::dev.off())
print(summary, row.names = FALSE)
cat(sprintf("\nWrote %d paired records to %s\n", nrow(records), destination))
