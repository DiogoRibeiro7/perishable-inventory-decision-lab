# Run from studies/orange_storage_decision:
# Rscript scripts/run_robust_policy.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/price_sensitivity.R")
source("R/robust_policy.R")
source("R/robust_evaluation.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) {
  stop("usage: Rscript scripts/run_robust_policy.R [number_of_lots] [output_directory]",
       call. = FALSE)
}
n_lots <- if (length(args) >= 1L) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) >= 2L) args[2] else "results/robust_policy"
settings <- list(n_lots = n_lots, simulation_seed = 20261024L,
                 price_seed = 20261025L, bootstrap_seed = 9188L, n_boot = 1000L,
                 decision_ratios = c(0.6, 0.8, 1),
                 decision_day = 12L, last_sale_day = 28L, delivery_lag_days = 2L,
                 storage_eur_per_kg_day = 0.001,
                 scenarios = robust_evaluation_scenarios(),
                 r_version = R.version.string, rng_kind = RNGkind())
records <- run_robust_policy_experiment(
  n_lots, settings$simulation_seed, settings$price_seed,
  settings$decision_ratios, settings$scenarios
)
set.seed(settings$bootstrap_seed)
summary <- summarize_robust_policy(records, settings$n_boot)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"),
            file.path(destination, "settings.R"), useBytes = TRUE)

lines <- c(
  "# Minimax-regret policy: fresh synthetic evaluation", "",
  sprintf("%d independent lots; one sale date fixed at day 12 for each policy.", n_lots),
  "The minimax policy considers terminal mean price ratios {0.6, 0.8, 1.0}.",
  "It minimises the largest fitted expected shortfall against each mean path's",
  "best sale date. All decisions precede held-out outcomes and price errors.",
  "The rule was motivated by the earlier price study; these lots and price",
  "innovations use fresh seeds, with no tuning to the evaluation results.", "",
  sprintf("Mean sale day: minimax %.2f; forecast-only stratified %.2f.",
          summary$mean_sale_day_robust[1], summary$mean_sale_day_stratified[1]),
  sprintf("Minimax sells earlier than forecast-only on %.1f%% of lots.",
          100 * mean(records$sale_day_robust < records$sale_day_stratified)), "",
  "## Mean realised net return per initially eligible 850-kg lot", "",
  "All returns are EUR, after storage and delivery rejection.", "",
  "| Evaluation scenario | Minimax | Forecast-only stratified | Pooled | Immediate |",
  "|---|---:|---:|---:|---:|"
)
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.2f | %.2f | %.2f | %.2f |", x$scenario,
    x$mean_robust_eur, x$mean_stratified_eur, x$mean_pooled_eur, x$mean_immediate_eur))
}
lines <- c(lines, "", "## Paired mean differences [95% lot-bootstrap interval]", "",
  "Intervals are marginal, without multiple-comparison adjustment. They describe",
  "mean contrasts under this generator, not individual-lot protection or field validity.", "",
  "| Scenario | Minimax - forecast-only | Minimax - pooled | Minimax - immediate |",
  "|---|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  cells <- vapply(c("stratified", "pooled", "immediate"), function(baseline) {
    prefix <- paste0("robust_minus_", baseline, "_")
    sprintf("%+.2f [%+.2f, %+.2f]", x[[paste0(prefix, "mean_eur")]],
            x[[paste0(prefix, "lower_95_eur")]], x[[paste0(prefix, "upper_95_eur")]])
  }, character(1))
  lines <- c(lines, paste0("| ", paste(c(x$scenario, cells), collapse = " | "), " |"))
}
lines <- c(lines, "", "## Descriptive downside against immediate sale", "",
  "Strict underperformance excludes exact ties; percentiles are empirical, not intervals.", "",
  "| Scenario | Minimax below immediate | Forecast-only below immediate | Minimax difference p10, EUR | Forecast-only difference p10, EUR |",
  "|---|---:|---:|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %.1f%% | %.1f%% | %+.2f | %+.2f |", x$scenario,
    100 * x$robust_below_immediate_fraction, 100 * x$stratified_below_immediate_fraction,
    x$robust_minus_immediate_p10_eur, x$stratified_minus_immediate_p10_eur))
}
lines <- c(lines, "", "![Policy tradeoffs](policy_tradeoffs.png)", "",
  "## Interpretation and reproduction", "",
  "The 60%-lower and 20%-higher terminal means lie outside the decision set.",
  "Even for a mean inside that set, random realised paths can lie outside it.",
  "Minimax regret bounds only fitted expected regret on the declared finite",
  "set: it does not guarantee a profit, beat immediate sale, or control a tail",
  "probability. The scenarios are assumptions, not calibrated market forecasts.",
  "All policies share each lot's inspections, fruit outcomes and price errors.",
  "Weibull deterioration, independent lots and shared grade shocks remain assumptions.", "",
  "From the project directory:", "", "```sh",
  sprintf("Rscript scripts/run_robust_policy.R %d", n_lots), "```", "",
  "[records.csv](records.csv), [summary.csv](summary.csv) and [settings.R](settings.R)",
  "provide paired outcomes, all metrics and the reproduction settings.",
  "See [ROBUST_POLICY.md](../../ROBUST_POLICY.md) for the criterion and limitations.")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)

grDevices::png(file.path(destination, "policy_tradeoffs.png"), width = 1600, height = 800, res = 140)
graphics::par(mfrow = c(1, 2), mar = c(5, 4.5, 4, 1))
labels <- c("Perfect\nforecast", "Unbiased\nnoise", "Mean\n20% lower",
            "Mean\n40% lower", "Mean\n60% lower", "Mean\n20% higher")
x <- seq_len(nrow(summary))
lower <- summary$robust_minus_stratified_lower_95_eur
upper <- summary$robust_minus_stratified_upper_95_eur
graphics::plot(x, summary$robust_minus_stratified_mean_eur, ylim = range(c(lower, upper, 0)),
                 xaxt = "n", xlab = "", ylab = "Mean paired difference (EUR per lot)",
                 main = "Minimax minus forecast-only", pch = 19, col = "#276a98", las = 1)
graphics::mtext("95% paired lot-bootstrap intervals", side = 3, line = 0.4, cex = 0.75)
graphics::abline(h = 0, col = "grey50", lty = 2)
graphics::arrows(x, lower, x, upper, angle = 90, code = 3, length = 0.05, col = "#276a98")
graphics::axis(1, x, labels, cex.axis = 0.72)
risk <- 100 * cbind(summary$robust_below_immediate_fraction,
                    summary$stratified_below_immediate_fraction)
graphics::matplot(x, risk, type = "b", pch = c(19, 17), lty = 1,
                   col = c("#276a98", "#b85a18"), ylim = c(0, max(risk) * 1.2 + 1),
                   xaxt = "n", xlab = "", ylab = "Lots earning less than immediate sale (%)",
                   main = "Observed downside", las = 1)
graphics::axis(1, x, labels, cex.axis = 0.72)
graphics::legend("topleft", c("Minimax", "Forecast-only stratified"),
                   col = c("#276a98", "#b85a18"), pch = c(19, 17), lty = 1, bty = "n", cex = 0.85)
invisible(grDevices::dev.off())
print(summary, row.names = FALSE)
cat(sprintf("\nWrote %d paired records to %s\n", nrow(records), destination))
