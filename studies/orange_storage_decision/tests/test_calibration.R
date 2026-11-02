# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/calibration.R")

expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}
calibration <- data.frame(day = c(5, 10), true_positive = c(8, 10),
  false_negative = c(2, 0), true_negative = c(9, 3), false_positive = c(1, 2))
rates <- inspection_calibration_rates(calibration, 12)
stopifnot(identical(rates, list(sensitivity = 0.9, specificity = 0.8,
                               n_acceptable = 20, n_unacceptable = 15)))
unequal <- calibration
unequal$true_positive[2] <- 90
unequal$false_negative[2] <- 10
stopifnot(inspection_calibration_rates(unequal, 12)$sensitivity == 98 / 110)
expect_error(inspection_calibration_rates(transform(calibration, day = 13), 12))
expect_error(inspection_calibration_rates(transform(calibration, true_positive = -1), 12))
expect_error(inspection_calibration_rates(transform(calibration, false_negative = 0.5), 12))
expect_error(inspection_calibration_rates(transform(calibration, true_negative = NA), 12))
expect_error(inspection_calibration_rates(transform(calibration, true_positive = 0, false_negative = 0), 12))
expect_error(inspection_calibration_rates(transform(calibration, true_positive = 0), 12))

inventory <- data.frame(cohort = c("eligible", "immature"), mass_kg = c(100, 30),
  initially_sellable = c(TRUE, FALSE), shape = c(2, 1), scale = c(25, 1))
inspections <- data.frame(cohort = "eligible", day = c(3, 6, 9, 12), n_checked = 500)
inspections$n_acceptable <- round(500 * (0.9 * exp(-(inspections$day / 25)^2) +
                                         0.2 * (1 - exp(-(inspections$day / 25)^2))))
prices <- data.frame(cohort = "eligible", day = 12:28,
  price_eur_per_kg = 0.8 + 0.04 * (12:28 - 12))
run <- function(cal = calibration, n = 6, stock = inventory) {
  bootstrap_calibrated_sale(inspections, stock, prices, cal, 0.001, 12, 2, 20, n)
}

# Independently reproduce both samples and the first paired refits. Training is
# generated under the ORIGINAL rates, not the re-estimated reference rates.
fit <- fit_weibull_by_cohort(inspections, inventory, 0.9, 0.8)
s <- exp(-(inspections$day / fit$scale)^fit$shape)
q <- 0.9 * s + 0.2 * (1 - s)
set.seed(924)
counts <- matrix(rbinom(6 * nrow(inspections), rep(500, 6 * nrow(inspections)),
                        rep(q, each = 6)), nrow = 6)
uniforms <- matrix(runif(12), nrow = 6)
se <- qbinom(uniforms[, 1], 20, 0.9) / 20
sp <- qbinom(uniforms[, 2], 15, 0.8) / 15
set.seed(924)
result <- run()
stopifnot(nrow(result$draws) == 12)
joint <- result$draws[result$draws$method == "recalibrated", ]
stopifnot(identical(joint$sensitivity, se), identical(joint$specificity, sp))
sampled <- transform(inspections, n_acceptable = counts[1, ])
for (method in c("conditional", "recalibrated")) {
  fit_rates <- if (method == "conditional") c(0.9, 0.8) else c(se[1], sp[1])
  refit <- fit_weibull_by_cohort(sampled, inventory, fit_rates[1], fit_rates[2])
  fitted <- with_fitted_survival(inventory, refit)
  day <- optimal_batch_sale(fitted, prices, 0.001, 12, 2)$sale_day
  mass <- 100 * exp(-(20 / refit$scale)^refit$shape)
  actual <- result$draws[result$draws$iteration == 1 & result$draws$method == method, ]
  stopifnot(actual$status == "success", actual$sale_day == day,
            isTRUE(all.equal(actual$acceptable_kg, mass)))
}

# Reference size changes must not alter point fits or the conditional bootstrap.
larger <- calibration
larger[-1] <- lapply(larger[-1], function(x) x * 100)
set.seed(924)
large_result <- run(larger)
stopifnot(identical(result$point_estimate, large_result$point_estimate))
stopifnot(identical(subset(result$draws, method == "conditional"),
                    subset(large_result$draws, method == "conditional")))
stopifnot(any(joint$sensitivity != subset(large_result$draws, method == "recalibrated")$sensitivity))
set.seed(924)
stopifnot(identical(result, run(stock = transform(inventory, shape = 7, scale = 100))))
expect_error(bootstrap_calibrated_sale(transform(inspections, day = day + 1),
  inventory, prices, calibration, 0.001, 12))
expect_error(bootstrap_calibrated_sale(inspections, inventory, prices, calibration,
  0.001, 12, prediction_day = 12))
expect_error(run(n = 0))

# Aggregate future mass across several fitted strata, excluding immature inventory.
multi_inventory <- rbind(inventory, transform(inventory[1, ], cohort = "second", mass_kg = 70))
multi_inspections <- rbind(inspections, transform(inspections, cohort = "second",
  n_acceptable = n_acceptable - 10))
multi_prices <- rbind(prices, transform(prices, cohort = "second"))
multi_fits <- fit_weibull_by_cohort(multi_inspections, multi_inventory, 0.9, 0.8)
set.seed(31)
multi <- bootstrap_calibrated_sale(multi_inspections, multi_inventory, multi_prices,
  calibration, 0.001, 12, 2, 20, 2)
expected_mass <- sum(c(100, 70) * exp(-(20 / multi_fits$scale)^multi_fits$shape))
stopifnot(isTRUE(all.equal(multi$point_estimate$acceptable_kg, expected_mass)),
          all(multi$draws$acceptable_kg >= 0 & multi$draws$acceptable_kg <= 170))

# A finite perfect calibration sample has a degenerate plug-in bootstrap.
# Preserve and document this limitation instead of inventing calibration variation.
perfect <- data.frame(day = 10, true_positive = 20, false_negative = 0,
                       true_negative = 20, false_positive = 0)
set.seed(81)
perfect_result <- run(perfect)
a <- subset(perfect_result$draws, method == "conditional", select = -method)
b <- subset(perfect_result$draws, method == "recalibrated", select = -method)
rownames(a) <- rownames(b) <- NULL
stopifnot(identical(a, b))

# Force one refit failure without changing later random samples or silently
# dropping attempts. The initial fit is call 1; conditional iteration 1 is call 2.
original_fit <- fit_weibull_by_cohort
calls <- 0L
fit_weibull_by_cohort <- function(...) {
  calls <<- calls + 1L
  if (calls == 2L) stop("deliberate test refit failure")
  original_fit(...)
}
set.seed(924)
failed <- run()
fit_weibull_by_cohort <- original_fit
stopifnot(failed$draws$status[1] == "fit_failure", is.na(failed$draws$sale_day[1]),
          identical(failed$draws[-1, ], result$draws[-1, ]))
summary <- summarize_calibration_bootstrap(failed$draws)
stopifnot(summary$attempted[1] == 6, summary$fit_failures[1] == 1,
          summary$successful[1] == 5)

# Invalid calibration draws are accounted for without rejecting and redrawing.
weak <- data.frame(day = 10, true_positive = 1, false_negative = 1,
                    true_negative = 1, false_positive = 0)
set.seed(721)
weak_result <- run(weak, 30)
bad <- weak_result$draws$status == "uninformative_calibration"
stopifnot(any(bad), all(is.na(weak_result$draws$sale_day[bad])),
          nrow(weak_result$draws) == 60,
          all(weak_result$draws$sensitivity[bad] + weak_result$draws$specificity[bad] <= 1))
weak_summary <- summarize_calibration_bootstrap(weak_result$draws)
stopifnot(weak_summary$calibration_failures[2] == sum(bad))

# Summary handles all-failed methods explicitly and rejects incomplete pairs.
none <- result$draws
none$status <- "fit_failure"
none$sale_day <- none$acceptable_kg <- NA_real_
none_summary <- summarize_calibration_bootstrap(none)
stopifnot(all(none_summary$successful == 0), all(is.na(none_summary$sale_day_median)))
expect_error(summarize_calibration_bootstrap(result$draws[-1, ]))
expect_error(summarize_calibration_bootstrap(rbind(result$draws, result$draws[1, ])))
expect_error(summarize_calibration_bootstrap(transform(result$draws, acceptable_kg = Inf)))
expect_error(summarize_calibration_bootstrap(transform(none, sale_day = 12)))
expect_error(summarize_calibration_bootstrap(transform(result$draws, sale_day = 12.5)))

# Sale-day percentiles retain observed whole days; mass uses interpolation.
manual <- result$draws
manual$sale_day <- rep(c(12, 13, 14, 15, 16, 28), each = 2)
manual$acceptable_kg <- rep(c(10, 20, 30, 40, 50, 60), each = 2)
manual_summary <- summarize_calibration_bootstrap(manual)
stopifnot(all(manual_summary$sale_day_lower_95 == 12),
          all(manual_summary$sale_day_median == 14),
          all(manual_summary$sale_day_upper_95 == 28),
          all(manual_summary$acceptable_kg_lower_95 == 11.25),
          all(manual_summary$acceptable_kg_median == 35),
          all(manual_summary$acceptable_kg_upper_95 == 58.75))

# Reconstruct the saved evidence directly from every retained bootstrap attempt.
saved <- utils::read.csv("results/calibration_uncertainty/draws.csv")
settings <- dget("results/calibration_uncertainty/settings.R")
stopifnot(nrow(saved) == 2 * settings$n_boot * length(settings$reference_per_class))
rebuilt <- do.call(rbind, lapply(settings$reference_per_class, function(n_reference) {
  cbind(reference_per_class = n_reference,
        summarize_calibration_bootstrap(saved[saved$reference_per_class == n_reference, ]))
}))
committed <- utils::read.csv("results/calibration_uncertainty/summary.csv")
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))

cat("Orange inspection calibration tests passed.\n")
