# Dependency-free tests. Run from the project directory:
# Rscript tests/test_model.R

source("R/model.R")
source("R/sampling.R")

expect_error <- function(expression) {
  observed <- tryCatch({
    force(expression)
    FALSE
  }, error = function(error) TRUE)
  stopifnot(observed)
}

# Weibull deterioration is monotone with exactly 100% survival at harvest.
stopifnot(identical(weibull_survival(0, 2, 10), 1))
stopifnot(all(diff(weibull_survival(0:30, 2, 10)) <= 0))
expect_error(weibull_survival(-1, 2, 10))
expect_error(weibull_survival(1:3, c(1, 2), 10))

# A deliberately simple scenario has distinct optimal selling dates.
inventory <- data.frame(
  cohort = c("A", "B", "immature"),
  mass_kg = c(100, 100, 5000),
  initially_sellable = c(TRUE, TRUE, FALSE),
  shape = c(2, 2, 1),
  scale = c(2, 100, 1),
  stringsAsFactors = FALSE
)
prices <- expand.grid(cohort = c("A", "B"), day = c(0, 10),
                      KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
prices$price_eur_per_kg <- c(3, 1, 4, 3)

joint <- optimal_batch_sale(inventory, prices, 0)
split <- optimal_split_sales(inventory, prices, 0)
stopifnot(joint$sale_day == 0)
stopifnot(split$sale_day[split$cohort == "A"] == 0)
stopifnot(split$sale_day[split$cohort == "B"] == 10)
stopifnot(sum(split$expected_net_eur) > joint$expected_net_eur)
stopifnot(joint$expected_gross_eur == 400)  # Initially immature fruit excluded.

# A price schedule with a missing cohort/day must fail explicitly.
expect_error(optimal_batch_sale(inventory, prices[-1, ], 0))
invalid_inventory <- inventory
invalid_inventory$mass_kg[1] <- -1
expect_error(optimal_batch_sale(invalid_inventory, prices, 0))
expect_error(optimal_batch_sale(inventory, prices, -1))

# Cross-sectional binomial inspection counts, without random test flakiness.
long_inventory <- inventory
long_inventory$shape[1:2] <- c(2, 2)
long_inventory$scale[1:2] <- c(15, 25)
inspections <- expand.grid(cohort = c("A", "B"), day = c(2, 5, 9, 12, 16),
                           KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
inspections$n_checked <- 1000L
position <- match(inspections$cohort, long_inventory$cohort)
inspections$n_acceptable <- round(
  inspections$n_checked * weibull_survival(
    inspections$day, long_inventory$shape[position], long_inventory$scale[position]
  )
)
fits <- fit_weibull_by_cohort(inspections, long_inventory)
stopifnot(nrow(fits) == 2L)
stopifnot(all(is.finite(fits$shape)), all(fits$shape > 0))
stopifnot(all(is.finite(fits$scale)), all(fits$scale > 0))
stopifnot(max(abs(fits$scale - c(15, 25))) < 3)
updated <- with_fitted_survival(long_inventory, fits)
stopifnot(all(updated$shape[1:2] > 0))
stopifnot(updated$initially_sellable[3] == FALSE)

# The information cut-off prevents future inspection leakage.
future_prices <- expand.grid(
  cohort = c("A", "B"), day = c(16, 20, 25),
  KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE
)
future_prices$price_eur_per_kg <- c(1.0, 1.0, 1.1, 1.2, 1.25, 1.4)
expect_error(bootstrap_sale_days(inspections, long_inventory, future_prices,
                                 0, decision_day = 12, n_boot = 5))
set.seed(42)
boot <- bootstrap_sale_days(inspections, long_inventory, future_prices,
                            0, decision_day = 16, n_boot = 20)
stopifnot(boot$attempted == 20L)
stopifnot(boot$failed >= 0L, boot$failed < 20L)
stopifnot(nrow(boot$decisions) + boot$failed == boot$attempted)
stopifnot(all(boot$decisions$sale_day >= 16))

cat("Orange storage decision tests passed.\n")
