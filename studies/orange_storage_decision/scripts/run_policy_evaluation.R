# Run from studies/orange_storage_decision:
# Rscript scripts/run_policy_evaluation.R [number_of_lots]
#
# All observations and price paths in this evaluation are simulated. Do not
# interpret the estimated effects as empirical orange-storage profitability.

source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 1L) {
  stop("usage: Rscript scripts/run_policy_evaluation.R [number_of_lots]",
       call. = FALSE)
}
n_lots <- if (length(args) == 0L) 100L else suppressWarnings(
  as.numeric(args[[1]])
)
assert_nonnegative_scalar(n_lots, "number_of_lots", integer = TRUE)
if (n_lots < 2L) {
  stop("number_of_lots must be at least two", call. = FALSE)
}

simulation_seed <- 20261022L
results <- run_policy_experiment(n_lots, simulation_seed)

# Bootstrap whole independent lots, preserving each lot's common prices,
# potential fruit lifetimes and differences between policy decisions.
set.seed(9187L)
report_difference <- function(description, differences) {
  interval <- paired_lot_interval(differences, n_boot = 1000L)
  cat(sprintf(
    "  %-39s %9.3f [%9.3f, %9.3f]\n",
    description, interval[["mean"]], interval[["lower_95"]],
    interval[["upper_95"]]
  ))
}

cat(sprintf("Synthetic prospective evaluation: %d independent lots\n", n_lots))
cat(sprintf("Random seed: %d; decision cutoff: day 12; delivery lag: 2 days\n",
            simulation_seed))
cat("Training days: 3/6/9/12; out-of-time scoring days: 16/20/24\n\n")

cat("Mean realised net return per eligible 850-kg batch (EUR):\n")
for (name in c("stratified", "pooled", "immediate", "oracle")) {
  column <- paste0("realised_", name, "_eur")
  cat(sprintf("  %-15s %9.2f\n", name, mean(results[[column]])))
}
cat("\nPaired differences, mean and lot-bootstrap 95% CI:\n")
report_difference(
  "Stratified - pooled net EUR",
  results$realised_stratified_eur - results$realised_pooled_eur
)
report_difference(
  "Stratified - immediate net EUR",
  results$realised_stratified_eur - results$realised_immediate_eur
)
report_difference(
  "Pooled - stratified Brier (positive better)",
  results$brier_pooled - results$brier_stratified
)
report_difference(
  "Pooled - stratified log loss (positive better)",
  results$log_loss_pooled - results$log_loss_stratified
)

cat(sprintf(
  "\nDifferent stratified and pooled sale days: %.1f%% of lots\n",
  100 * mean(results$sale_day_stratified != results$sale_day_pooled)
))
cat("The oracle knows the generating survival curves but not realised lives.\n")
cat("Intervals describe simulation-to-simulation variation, not field validity.\n")
