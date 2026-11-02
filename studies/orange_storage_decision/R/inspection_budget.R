# Source model, sampling, evaluation, simulation, shared_shape,
# shared_shape_evaluation and shape_ensemble first. Base R only.

validate_inspection_budgets <- function(budgets) {
  if (!is.numeric(budgets) || !length(budgets) || any(!is.finite(budgets)) ||
      any(budgets <= 0 | budgets != floor(budgets)) || anyDuplicated(budgets)) {
    stop("budgets must be distinct positive whole inspection counts", call. = FALSE)
  }
  invisible(TRUE)
}

#' Compare fixed inspection plans using common training and future random numbers.
#' @param n_lots Independent base lots per scenario and inspection plan.
#' @param training_seed Seed reset for each plan's inventory, prices and training uniforms.
#' @param outcome_seed Separate seed reset for each plan's future outcomes.
#' @param budgets Inspection counts per stratum/day, declared before running any plan.
#' @param scenarios Prespecified generating shape regimes.
#' @return Paired records with inspection counts; original returns exclude inspection cost.
run_inspection_budget_experiment <- function(n_lots = 200L, training_seed = 20261106L,
                                             outcome_seed = 20261107L,
                                             budgets = c(30L, 90L, 180L),
                                             scenarios = default_shape_scenarios()) {
  validate_inspection_budgets(budgets)
  result <- do.call(rbind, lapply(budgets, function(budget) {
    tryCatch({
      records <- run_shape_ensemble_experiment(n_lots, training_seed, outcome_seed,
        scenarios, training_per_group = budget)
      records$per_group <- budget
      # Two eligible strata, each inspected on days 3/6/9/12.
      records$inspection_count <- 8 * budget
      records
    }, error = function(error) {
      stop(sprintf("inspection budget %d: %s", budget, conditionMessage(error)), call. = FALSE)
    })
  }))
  rownames(result) <- NULL
  result
}

validate_budget_records <- function(records) {
  fields <- c("lot_id", "per_group", "inspection_count", "realised_immediate_eur")
  for (model in c("separate", "shared", "ensemble")) {
    fields <- c(fields, paste0("sale_day_", model), paste0("realised_", model, "_eur"),
                paste0("brier_", model), paste0("log_loss_", model))
  }
  if (!is.data.frame(records) || !nrow(records) || !all(c("scenario", fields) %in% names(records)) ||
      !is.character(records$scenario) || anyNA(records$scenario) ||
      any(!nzchar(trimws(records$scenario))) ||
      any(!vapply(records[fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1))) ||
      any(records$lot_id <= 0 | records$lot_id != floor(records$lot_id)) ||
      length(unique(records$lot_id)) < 2L) {
    stop("budget records need finite measurements from at least two paired lots", call. = FALSE)
  }
  validate_inspection_budgets(unique(records$per_group))
  if (any(records$inspection_count != 8 * records$per_group) ||
      any(table(records$lot_id, records$scenario, records$per_group) != 1L)) {
    stop("records must cover every lot/scenario/budget exactly once with correct inspection totals", call. = FALSE)
  }
  # The immediate policy needs no inspection and has the same outcome under every plan.
  groups <- split(records, interaction(records$lot_id, records$scenario, drop = TRUE))
  if (any(vapply(groups, function(x) length(unique(x$realised_immediate_eur)) != 1L, logical(1)))) {
    stop("inspection plans must share each lot's immediate-sale outcome", call. = FALSE)
  }
  invisible(TRUE)
}

#' Summarise prediction and economic performance at hypothetical inspection prices.
#' @param records Output of run_inspection_budget_experiment().
#' @param costs Nonnegative EUR per inspected fruit; each cost applies to all plans.
#' @return One row per scenario, plan, fitted policy and inspection unit cost.
summarize_inspection_budgets <- function(records, costs = c(0, 0.02, 0.05, 0.10)) {
  validate_budget_records(records)
  if (!is.numeric(costs) || !length(costs) || any(!is.finite(costs)) || any(costs < 0) || anyDuplicated(costs)) {
    stop("costs must be distinct finite nonnegative EUR amounts", call. = FALSE)
  }
  grid <- expand.grid(scenario = sort(unique(records$scenario)),
    per_group = sort(unique(records$per_group)), model = c("separate", "shared", "ensemble"),
    cost_eur_per_inspection = sort(costs), KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
  do.call(rbind, lapply(seq_len(nrow(grid)), function(i) {
    row <- grid[i, ]
    part <- records[records$scenario == row$scenario & records$per_group == row$per_group, ]
    sale_return <- part[[paste0("realised_", row$model, "_eur")]]
    cost <- part$inspection_count * row$cost_eur_per_inspection
    net <- sale_return - cost
    row$n_lots <- nrow(part)
    row$inspection_count <- part$inspection_count[1]
    row$mean_brier <- mean(part[[paste0("brier_", row$model)]])
    row$mean_log_loss <- mean(part[[paste0("log_loss_", row$model)]])
    row$mean_sale_day <- mean(part[[paste0("sale_day_", row$model)]])
    row$mean_sale_return_eur <- mean(sale_return)
    row$mean_inspection_cost_eur <- mean(cost)
    row$mean_net_return_eur <- mean(net)
    row$mean_net_minus_immediate_eur <- mean(net - part$realised_immediate_eur)
    row$below_immediate_fraction <- mean(net < part$realised_immediate_eur)
    row
  }))
}

#' Paired plan differences and break-even cost of each additional inspection.
#' @param records Complete paired study records.
#' @param n_boot Number of whole-lot resamples for marginal percentile intervals.
#' @return Comparisons of every higher budget with the smallest supplied budget.
compare_inspection_budgets <- function(records, n_boot = 1000L) {
  validate_budget_records(records)
  budgets <- sort(unique(records$per_group))
  if (length(budgets) < 2L) stop("budget comparison requires at least two plans", call. = FALSE)
  grid <- expand.grid(scenario = sort(unique(records$scenario)), per_group = budgets[-1],
    model = c("separate", "shared", "ensemble"), KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
  do.call(rbind, lapply(seq_len(nrow(grid)), function(i) {
    row <- grid[i, ]
    reference <- records[records$scenario == row$scenario & records$per_group == budgets[1], ]
    reference <- reference[order(reference$lot_id), ]
    larger <- records[records$scenario == row$scenario & records$per_group == row$per_group, ]
    larger <- larger[match(reference$lot_id, larger$lot_id), ]
    row$reference_per_group <- budgets[1]
    row$n_lots <- nrow(reference)
    extra <- larger$inspection_count[1] - reference$inspection_count[1]
    row$additional_inspections <- extra
    fields <- c(paste0("realised_", row$model, "_eur"), paste0("brier_", row$model),
                paste0("log_loss_", row$model))
    contrasts <- c("return_gain_eur", "brier_improvement", "log_loss_improvement")
    for (j in seq_along(fields)) {
      difference <- larger[[fields[j]]] - reference[[fields[j]]]
      if (j > 1L) difference <- -difference
      interval <- paired_lot_interval(difference, n_boot)
      for (statistic in names(interval)) row[[paste0(contrasts[j], "_", statistic)]] <- unname(interval[statistic])
    }
    for (statistic in c("mean", "lower_95", "upper_95")) {
      row[[paste0("break_even_eur_per_extra_inspection_", statistic)]] <-
        row[[paste0("return_gain_eur_", statistic)]] / extra
    }
    row$larger_below_reference_fraction <- mean(larger[[fields[1]]] < reference[[fields[1]]])
    row
  }))
}
