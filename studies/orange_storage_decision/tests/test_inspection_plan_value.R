# Run from studies/orange_storage_decision. Base R only.
source("R/model.R")
source("R/sampling.R")
source("R/evaluation.R")
source("R/simulation.R")
source("R/shared_shape.R")
source("R/shape_ensemble.R")
source("R/inspection_removals.R")
source("R/inspection_plan_value.R")
expect_error <- function(expression) {
  stopifnot(tryCatch({ force(expression); FALSE }, error = function(error) TRUE))
}

stock <- data.frame(cohort = c("early", "late", "immature"), mass_kg = c(100, 50, 30),
  initially_sellable = c(TRUE, TRUE, FALSE), shape = 1, scale = 20)
ledger <- data.frame(cohort = stock$cohort, day = c(3, 8, 1), mass_kg = c(20, 10, 10))
stopifnot(abs(predecision_holding_cost(stock, ledger, 0.001, 12) - 1.58) < 1e-12,
          predecision_holding_cost(stock, ledger, 0, 12) == 0,
          predecision_holding_cost(stock, ledger[FALSE, ], 0.001, 12) == 1.8)
full <- data.frame(cohort = stock$cohort[1:2], day = 0, mass_kg = c(100, 50))
stopifnot(predecision_holding_cost(stock, full, 0.001, 12) == 0,
          predecision_holding_cost(stock, transform(full, day = 12), 0.001, 12) == 1.8)
expect_error(predecision_holding_cost(stock, transform(ledger, day = 13), 0.001, 12))
expect_error(predecision_holding_cost(stock, transform(ledger, mass_kg = 200), 0.001, 12))
expect_error(predecision_holding_cost(stock, ledger, -1, 12))

# Each sample is disjoint across days; budgets share nested prefixes per day.
times <- list(early = rep(20, 800), late = rep(0, 900))
set.seed(23)
roster <- plan_value_roster(times)
small <- plan_value_observations(roster, 30)
medium <- plan_value_observations(roster, 90)
large <- plan_value_observations(roster, 180)
key <- function(x) paste(x$cohort, x$fruit_id)
stopifnot(nrow(roster) == 1440L, !anyDuplicated(key(roster)),
          all(key(small$selected) %in% key(medium$selected)),
          all(key(medium$selected) %in% key(large$selected)),
          all(small$inspections$n_checked == 30), sum(small$removals$mass_kg) == 48,
          all(roster$reported_acceptable %in% 0:1),
          all(table(roster$cohort, roster$day) == 180))
# Changing only post-cutoff failure times cannot alter observed counts or samples.
set.seed(23)
future_changed <- plan_value_roster(list(early = rep(80, 800), late = rep(0, 900)))
stopifnot(identical(roster, future_changed))
expect_error(plan_value_roster(list(early = rep(20, 719))))
expect_error(plan_value_roster(times, days = c(3, 3)))
expect_error(plan_value_observations(roster, 181))
expect_error(plan_value_observations(roster, 0))

# Hand-computed finite population: removing already failed fruit saves holding
# cost, so the net removal cost is allowed to be negative.
tiny <- transform(stock, mass_kg = c(0.6, 0.4, 0.2))
prices <- expand.grid(cohort = c("early", "late"), day = c(12, 16), stringsAsFactors = FALSE)
prices$price_eur_per_kg <- 1
lot <- list(truth = tiny, prices = prices, lifetimes = list(early = c(5, 20, 40), late = c(10, 40)))
plan <- list(removals = data.frame(cohort = c("early", "late"), day = c(3, 6), mass_kg = 0.2),
  selected = data.frame(cohort = c("early", "late"), fruit_id = 1))
score <- score_plan_value(lot, plan, list(sale_day = 16L, weight_shared = 0.5))
stopifnot(abs(score$return_before_labour_eur - 0.5874) < 1e-12,
          abs(score$predecision_storage_eur - 0.009) < 1e-12,
          abs(score$no_inspection_day12_eur - 0.586) < 1e-12,
          abs(score$no_inspection_day16_eur - 0.582) < 1e-12,
          abs(score$removal_net_cost_eur + 0.0038) < 1e-12,
          abs(score$timing_gain_eur + 0.0024) < 1e-12)
# Removing a surviving fruit instead excludes precisely its own sale revenue.
plan$selected$fruit_id[1] <- 2
other <- score_plan_value(lot, plan, list(sale_day = 16L, weight_shared = 0.5))
stopifnot(abs(score$return_before_labour_eur - other$return_before_labour_eur - 0.2) < 1e-12)

# Fit sees only the allowed aggregate inputs and no true survival parameters.
# Every lot's three policies must be fixed before any outcome is scored.
original_policy <- fit_plan_value_policy
original_score <- score_plan_value
calls <- 0L
scores <- 0L
fit_plan_value_policy <- function(inspections, inventory, prices, removals) {
  calls <<- calls + 1L
  stopifnot(setequal(names(inspections), c("cohort", "day", "n_acceptable", "n_checked")),
            max(inspections$day) == 12, max(removals$day) == 12,
            all(inventory$shape == 1), all(inventory$scale == 1))
  original_policy(inspections, inventory, prices, removals)
}
score_plan_value <- function(lot, plan, policy) {
  stopifnot(calls == 3L * (scores %/% 3L + 1L))
  scores <<- scores + 1L
  original_score(lot, plan, policy)
}
records <- run_plan_value_experiment(2, 925, 416, 725)
fit_plan_value_policy <- original_policy
score_plan_value <- original_score
stopifnot(calls == 6L, scores == 6L, nrow(records) == 6L)
validate_plan_value_records(records)
stopifnot(all(abs(records$return_before_labour_eur - records$no_inspection_day12_eur -
                    records$timing_gain_eur + records$removal_net_cost_eur) < 1e-10),
          all(abs(records$predecision_storage_eur -
                    (10.2 - records$removed_eligible_kg * 4.5 * 0.001)) < 1e-10))
expect_error(run_plan_value_experiment(1))

manual <- records
manual$return_before_labour_eur <- rep(c(120, 130), each = 3)
manual$same_plan_day12_before_labour_eur <- 108
manual$no_inspection_day12_eur <- 100
manual$no_inspection_day16_eur <- 110
manual$timing_gain_eur <- manual$return_before_labour_eur - 108
manual$removal_net_cost_eur <- -8
set.seed(22)
summary <- summarize_plan_value(manual, c(0, 0.02), 100)
free <- subset(summary, per_group == 30 & labour_eur_per_check == 0)
paid <- subset(summary, per_group == 30 & labour_eur_per_check == 0.02)
stopifnot(abs(paid$gain_vs_day12_eur_mean - 20.2) < 1e-12,
          abs(paid$gain_vs_day16_eur_mean - 10.2) < 1e-12,
          paid$timing_gain_eur_mean == 17, paid$removal_net_cost_eur_mean == -8,
          free$break_even_labour_vs_day12_mean == 25 / 240,
          abs(free$gain_vs_day12_eur_lower_95 - paid$gain_vs_day12_eur_lower_95 - 4.8) < 1e-12)
set.seed(22)
stopifnot(identical(summary, summarize_plan_value(manual[6:1, ], c(0.02, 0), 100)))
expect_error(summarize_plan_value(records[-1, ]))
expect_error(summarize_plan_value(rbind(records, records[1, ])))
expect_error(summarize_plan_value(transform(records, no_inspection_day16_eur = seq_len(6))))
expect_error(summarize_plan_value(transform(records, remaining_eligible_kg = 1)))
expect_error(summarize_plan_value(transform(records, timing_gain_eur = Inf)))
expect_error(summarize_plan_value(records, c(0, -1)))

saved <- read.csv("results/inspection_plan_value/records.csv")
settings <- dget("results/inspection_plan_value/settings.R")
set.seed(settings$bootstrap_seed)
rebuilt <- summarize_plan_value(saved, settings$costs, settings$n_boot)
reported <- read.csv("results/inspection_plan_value/summary.csv")
stopifnot(nrow(saved) == 3L * settings$n_lots,
          isTRUE(all.equal(rebuilt, reported, tolerance = 1e-10)))
cat("Orange inspection plan value tests passed.\n")
