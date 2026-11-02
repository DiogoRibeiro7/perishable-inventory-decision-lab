# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shared_shape_evaluation.R")
source("R/shape_ensemble.R")
source("R/inspection_budget.R")
expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

# Explicit economics: 480 extra checks earn EUR 15 before inspection charges.
small <- data.frame(lot_id = rep(1:2, 2), scenario = "common_shape", per_group = rep(c(30, 90), each = 2),
  inspection_count = rep(c(240, 720), each = 2), realised_immediate_eur = rep(c(105, 115), 2))
for (model in c("separate", "shared", "ensemble")) {
  small[[paste0("sale_day_", model)]] <- c(12, 15, 14, 16)
  small[[paste0("realised_", model, "_eur")]] <- c(100, 120, 110, 140)
  small[[paste0("brier_", model)]] <- c(0.2, 0.3, 0.15, 0.25)
  small[[paste0("log_loss_", model)]] <- c(0.6, 0.8, 0.5, 0.7)
}
set.seed(53)
contrasts <- compare_inspection_budgets(small, 100)
stopifnot(all(contrasts$return_gain_eur_mean == 15),
          all(contrasts$return_gain_eur_lower_95 == 10), all(contrasts$return_gain_eur_upper_95 == 20),
          all(contrasts$additional_inspections == 480),
          all(contrasts$break_even_eur_per_extra_inspection_mean == 15 / 480),
          all(abs(contrasts$brier_improvement_mean - 0.05) < 1e-12))
original <- small
summary <- summarize_inspection_budgets(small, c(0, 0.02, 0.05))
at_two_cents <- subset(summary, model == "ensemble" & cost_eur_per_inspection == 0.02)
stopifnot(identical(original, small),
          isTRUE(all.equal(at_two_cents$mean_net_return_eur, c(105.2, 110.6))),
          isTRUE(all.equal(at_two_cents$mean_inspection_cost_eur, c(4.8, 14.4))),
          all(at_two_cents$below_immediate_fraction == 0.5))
at_break_even <- summarize_inspection_budgets(small, 15 / 480)
stopifnot(length(unique(at_break_even$mean_net_return_eur)) == 1L)
negative <- small
negative$realised_ensemble_eur[3:4] <- c(90, 100)
stopifnot(subset(compare_inspection_budgets(negative, 100), model == "ensemble")$
            break_even_eur_per_extra_inspection_mean < 0)
set.seed(53)
shuffled <- compare_inspection_budgets(small[c(4, 2, 1, 3), ], 100)
stopifnot(identical(contrasts, shuffled))

expect_error(validate_inspection_budgets(c(30, 30)))
expect_error(validate_inspection_budgets(c(0, 30)))
expect_error(validate_inspection_budgets(c(30, 90.5)))
expect_error(validate_inspection_budgets(c(30, Inf)))
expect_error(validate_inspection_budgets(numeric()))
expect_error(compare_inspection_budgets(small[-1, ]))
expect_error(compare_inspection_budgets(rbind(small, small[1, ])))
expect_error(compare_inspection_budgets(subset(small, per_group == 30)))
expect_error(summarize_inspection_budgets(transform(small, inspection_count = 1)))
expect_error(summarize_inspection_budgets(transform(small, brier_ensemble = Inf)))
expect_error(summarize_inspection_budgets(small, c(0, -0.1)))
expect_error(summarize_inspection_budgets(small, c(0, 0)))
bad <- small
bad$realised_immediate_eur[3] <- 999
expect_error(compare_inspection_budgets(bad))
expect_error(run_shape_ensemble_experiment(2, training_per_group = 0))
expect_error(run_shared_shape_experiment(2, training_per_group = 1.5))

# Every fit receives the declared number of past inspections and public metadata.
original_fitter <- fit_ensemble_shape_policy
seen <- numeric()
fit_ensemble_shape_policy <- function(inspections, inventory, prices, method) {
  stopifnot(nrow(inspections) == 8L, max(inspections$day) == 12L,
            all(inventory$shape == 1), all(inventory$scale == 1),
            length(unique(inspections$n_checked)) == 1L)
  seen <<- c(seen, inspections$n_checked[1])
  original_fitter(inspections, inventory, prices, method)
}
scenarios <- default_shape_scenarios()[1, ]
paired <- run_inspection_budget_experiment(3, 685, 915, c(30, 90, 180), scenarios)
fit_ensemble_shape_policy <- original_fitter
stopifnot(identical(sort(unique(seen)), c(30, 90, 180)), length(seen) == 18L)
same_outcomes <- split(paired$realised_immediate_eur, paired$lot_id)
stopifnot(all(vapply(same_outcomes, function(x) length(unique(x)) == 1L, logical(1))))

# Defaults reproduce the original ensemble; plans share innovations, not truth inputs.
baseline <- run_shape_ensemble_experiment(3, 685, 915, scenarios)
largest <- subset(paired, per_group == 180)[names(baseline)]
rownames(largest) <- NULL
stopifnot(identical(largest, baseline))
other <- run_inspection_budget_experiment(3, 685, 916, c(30, 90, 180), scenarios)
fixed <- c("per_group", "sale_day_ensemble", "sale_day_separate", "sale_day_shared",
  "ensemble_weight_shared", "ensemble_nll_separate", "ensemble_nll_shared")
stopifnot(identical(paired[fixed], other[fixed]), any(paired$brier_ensemble != other$brier_ensemble))
sort_records <- function(x) {
  x <- x[order(x$per_group, x$scenario, x$lot_id), ]
  rownames(x) <- NULL
  x
}
reversed <- run_inspection_budget_experiment(3, 685, 915, c(180, 90, 30), scenarios)
stopifnot(identical(sort_records(paired), sort_records(reversed)))
subset_plan <- run_inspection_budget_experiment(3, 685, 915, 90, scenarios)
stopifnot(identical(sort_records(subset_plan), sort_records(subset(paired, per_group == 90))))

# The unchanged default reproduces the first three lots of the previous study.
legacy <- run_shape_ensemble_experiment(3)
legacy_saved <- subset(utils::read.csv("results/shape_ensemble/records.csv"), lot_id <= 3)
# Allow small optimiser differences across R releases/platforms.
stopifnot(isTRUE(all.equal(legacy, legacy_saved, tolerance = 1e-6)))

# Reconstruct the saved summaries and bootstrap comparisons from paired evidence.
saved <- utils::read.csv("results/inspection_budget/records.csv")
settings <- dget("results/inspection_budget/settings.R")
stopifnot(nrow(saved) == settings$n_lots * length(settings$budgets) * nrow(settings$scenarios))
rebuilt <- summarize_inspection_budgets(saved, settings$costs_eur_per_inspection)
committed <- utils::read.csv("results/inspection_budget/summary.csv")
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))
set.seed(settings$bootstrap_seed)
rebuilt <- compare_inspection_budgets(saved, settings$n_boot)
committed <- utils::read.csv("results/inspection_budget/contrasts.csv")
stopifnot(isTRUE(all.equal(rebuilt, committed, tolerance = 1e-10)))

cat("Orange inspection budget tests passed.\n")
