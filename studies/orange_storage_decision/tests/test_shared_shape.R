# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shared_shape_evaluation.R")

expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}
inventory <- data.frame(cohort = c("early", "late", "immature"), mass_kg = c(100, 100, 30),
  initially_sellable = c(TRUE, TRUE, FALSE), shape = c(2, 2, 1), scale = c(18, 35, 1))
train <- expand.grid(cohort = c("early", "late"), day = c(3, 6, 9, 12),
                       KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
train$n_checked <- 100000
index <- match(train$cohort, inventory$cohort)
s <- exp(-(train$day / inventory$scale[index])^2)
train$n_acceptable <- round(train$n_checked * (0.9 * s + 0.15 * (1 - s)))
fit <- fit_shared_shape_weibull(train, inventory, 0.9, 0.85)
stopifnot(length(unique(fit$shape)) == 1, abs(fit$shape[1] - 2) < 0.002,
          max(abs(fit$scale - c(18, 35))) < 0.02)
stopifnot(identical(fit, fit_shared_shape_weibull(train[8:1, ], inventory[3:1, ], 0.9, 0.85)))
stopifnot(identical(fit, fit_shared_shape_weibull(train,
  transform(inventory, shape = 7, scale = 100, mass_kg = c(10, 500, 90)), 0.9, 0.85)))
stopifnot(identical(fit_shared_shape_weibull(train, inventory),
                    fit_shared_shape_weibull(train, inventory, 1, 1)))
one <- inventory[c(1, 3), ]
one_train <- train[train$cohort == "early", ]
stopifnot(identical(fit_shared_shape_weibull(one_train, one, 0.9, 0.85),
                    fit_weibull_by_cohort(one_train, one, 0.9, 0.85)))
expect_error(fit_shared_shape_weibull(train, inventory, 0.4, 0.5))
expect_error(fit_shared_shape_weibull(train[5:8, ], inventory))
expect_error(fit_shared_shape_weibull(transform(train, n_acceptable = n_checked + 1), inventory))

# Independently reconstruct the binomial objective and compare nested restrictions.
p <- exp(-(train$day / fit$scale[match(train$cohort, fit$cohort)])^fit$shape[1])
loss <- -sum(dbinom(train$n_acceptable, train$n_checked, 0.9 * p + 0.15 * (1 - p), log = TRUE))
stopifnot(isTRUE(all.equal(sum(fit$negative_log_likelihood), loss)))
separate <- fit_weibull_by_cohort(train, inventory, 0.9, 0.85)
pooled <- fit_pooled_weibull(train, inventory, 0.9, 0.85)
stopifnot(sum(separate$negative_log_likelihood) <= loss + 1e-4,
          loss <= pooled$objective + 1e-4)

# With strongly different generating shapes the shared model cannot fit both curves.
different <- train
true_shapes <- c(1, 3.5)[match(train$cohort, c("early", "late"))]
p <- exp(-(train$day / inventory$scale[index])^true_shapes)
different$n_acceptable <- round(train$n_checked * (0.9 * p + 0.15 * (1 - p)))
restricted <- fit_shared_shape_weibull(different, inventory, 0.9, 0.85)
unrestricted <- fit_weibull_by_cohort(different, inventory, 0.9, 0.85)
stopifnot(sum(restricted$negative_log_likelihood) > sum(unrestricted$negative_log_likelihood) + 10)

# Inspection coupling follows an independently specified inverse binomial CDF.
uniforms <- rep(0.5, 8)
sampled <- shape_study_inspections(inventory, c(3, 6, 9, 12), 100, uniforms, 0.9, 0.85)
stopifnot(identical(sampled$n_acceptable, qbinom(uniforms, 100, 0.9 * s + 0.15 * (1 - s))))
expect_error(shape_study_inspections(inventory, c(3, 6, 9, 12), 100, rep(1, 8)))

# No future information exists until all policies have been chosen.
original_policy <- fit_shape_policy
original_outcomes <- shape_study_outcome_uniforms
calls <- 0L
fit_shape_policy <- function(...) {
  calls <<- calls + 1L
  original_policy(...)
}
shape_study_outcome_uniforms <- function(...) {
  stopifnot(calls == 2 * 3 * 2)
  original_outcomes(...)
}
invisible(run_shared_shape_experiment(2, 741, 851))
fit_shape_policy <- original_policy
shape_study_outcome_uniforms <- original_outcomes

paired <- run_shared_shape_experiment(5, 741, 851)
settings <- default_shape_scenarios()
sort_records <- function(x) {
  x <- x[order(x$lot_id, x$scenario), ]
  rownames(x) <- NULL
  x
}
reversed <- run_shared_shape_experiment(5, 741, 851, settings[3:1, ])
stopifnot(identical(sort_records(paired), sort_records(reversed)))
single <- run_shared_shape_experiment(5, 741, 851, settings[2, ])
stopifnot(identical(sort_records(single), sort_records(paired[paired$scenario == "nearby_shapes", ])))
other_outcomes <- run_shared_shape_experiment(5, 741, 999)
training_fields <- c("sale_day_separate", "sale_day_shared", "shape_separate_advanced",
  "shape_separate_intermediate", "shape_shared_advanced", "shape_shared_intermediate")
stopifnot(identical(paired[training_fields], other_outcomes[training_fields]),
          any(paired$realised_immediate_eur != other_outcomes$realised_immediate_eur))
stopifnot(all(paired$shape_shared_advanced == paired$shape_shared_intermediate))
common <- paired[paired$scenario == "common_shape", ]
stopifnot(all(common$true_shape_advanced == common$true_shape_intermediate))
expect_error(run_shared_shape_experiment(1))
expect_error(run_shared_shape_experiment(2, scenarios = transform(settings, advanced_shape = NA)))
prices <- data.frame(cohort = rep(c("early", "late"), each = 17), day = rep(12:28, 2),
                       price_eur_per_kg = 1)
expect_error(fit_shape_policy(transform(train, day = day + 1), inventory, prices, "shared"))

small <- paired[paired$scenario == "common_shape", ][1:2, ]
small$realised_shared_eur <- c(10, 30)
small$realised_separate_eur <- c(20, 20)
small$realised_immediate_eur <- c(15, 20)
small$brier_separate <- c(0.3, 0.2)
small$brier_shared <- c(0.2, 0.1)
set.seed(11)
summary <- summarize_shared_shape(small, 100)
stopifnot(summary$shared_minus_separate_eur_mean == 0,
          summary$shared_minus_immediate_eur_mean == 2.5,
          isTRUE(all.equal(summary$brier_improvement_mean, 0.1)),
          summary$shared_below_immediate_fraction == 0.5)
expect_error(summarize_shared_shape(paired[-1, ]))
expect_error(summarize_shared_shape(rbind(paired, paired[1, ])))
expect_error(summarize_shared_shape(transform(paired, brier_shared = Inf)))

# Saved paired evidence reconstructs its declared bootstrap summary exactly.
saved <- utils::read.csv("results/shared_shape/records.csv")
settings <- dget("results/shared_shape/settings.R")
stopifnot(nrow(saved) == settings$n_lots * nrow(settings$scenarios))
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_shared_shape(saved, settings$n_boot)
committed <- utils::read.csv("results/shared_shape/summary.csv")
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))

cat("Orange shared-shape model tests passed.\n")
