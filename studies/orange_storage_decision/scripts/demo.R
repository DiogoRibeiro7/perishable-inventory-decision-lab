# Reproducible, synthetic illustration. Run from the project directory:
# Rscript scripts/demo.R

source("R/model.R")
source("R/sampling.R")

set.seed(20261022)

# The three strata share a harvest date, not a physiological maturity stage.
# All parameter values and prices below are illustrative, not observations.
inventory <- data.frame(
  cohort = c("advanced", "intermediate", "initially_immature"),
  mass_kg = c(450, 400, 150),
  initially_sellable = c(TRUE, TRUE, FALSE),
  shape = c(2.2, 2, 1),
  scale = c(18, 38, 1),
  stringsAsFactors = FALSE
)

# Destructive cross-sectional samples are assumed independent and
# representative within each predefined, initially eligible stratum.
inspections <- expand.grid(
  cohort = c("advanced", "intermediate"),
  day = c(4, 8, 12, 16),
  KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE
)
inspections$n_checked <- 250L
position <- match(inspections$cohort, inventory$cohort)
inspections$n_acceptable <- stats::rbinom(
  nrow(inspections), size = inspections$n_checked,
  prob = weibull_survival(inspections$day,
                          inventory$shape[position], inventory$scale[position])
)

# At day 16, only inspections from days 4, 8, 12 and 16 are available.
decision_day <- 16L
estimates <- fit_weibull_by_cohort(inspections, inventory)
calibrated_inventory <- with_fitted_survival(inventory, estimates)

prices <- expand.grid(
  cohort = c("advanced", "intermediate"),
  day = decision_day:32L,
  KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE
)
prices$price_eur_per_kg <- ifelse(
  prices$cohort == "advanced",
  0.84 + 0.008 * (prices$day - decision_day),
  0.78 + 0.030 * (prices$day - decision_day)
)

storage_cost <- 0.001  # EUR per initial saleable kg per day
delivery_lag <- 2L     # freshness must hold at delivery, not just at sale

joint <- optimal_batch_sale(calibrated_inventory, prices, storage_cost,
                            decision_day, delivery_lag)
split <- optimal_split_sales(calibrated_inventory, prices, storage_cost,
                             decision_day, delivery_lag)
uncertainty <- bootstrap_sale_days(inspections, inventory, prices,
                                   storage_cost, decision_day, delivery_lag,
                                   n_boot = 100L)

cat("SYNTHETIC ORANGE STORAGE STUDY (NOT EMPIRICAL EVIDENCE)\n\n")
cat("Weibull fits from inspections observed no later than day 16:\n")
print(estimates, row.names = FALSE)
cat("\nWhole-batch expected-value decision:\n")
print(joint, row.names = FALSE)
cat("\nIndependent stratum sales (no extra transaction costs):\n")
print(split, row.names = FALSE)
cat(sprintf("\nIllustrative split value improvement: EUR %.2f\n",
            sum(split$expected_net_eur) - joint$expected_net_eur))
cat(sprintf("\nBootstrap refits: %d successful / %d attempted\n",
            nrow(uncertainty$decisions), uncertainty$attempted))
cat("Optimal whole-batch sale-day frequencies:\n")
print(table(uncertainty$decisions$sale_day))
