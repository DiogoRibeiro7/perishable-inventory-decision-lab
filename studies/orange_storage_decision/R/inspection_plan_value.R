# Source model, sampling, evaluation, simulation, shared_shape,
# shape_ensemble and inspection_removals first. Base R only.

#' Holding cost from harvest through the decision cutoff, allowing past removals.
#' @param inventory Initial inventory; only initially eligible mass incurs this cost.
#' @param removals Observed random-removal ledger, as in inspection_remaining_mass().
#' @param storage_eur_per_kg_day Nonnegative holding cost per physical kg/day.
#' @param decision_day Whole-day information cutoff.
#' @return EUR incurred before the cutoff, excluding subsequent holding costs.
predecision_holding_cost <- function(inventory, removals, storage_eur_per_kg_day, decision_day) {
  inspection_remaining_mass(inventory, removals, decision_day)
  assert_nonnegative_scalar(storage_eur_per_kg_day, "storage_eur_per_kg_day")
  eligible <- inventory$cohort[inventory$initially_sellable]
  ledger <- removals[removals$cohort %in% eligible, , drop = FALSE]
  kg_days <- sum(inventory$mass_kg[inventory$initially_sellable]) * decision_day -
    sum(ledger$mass_kg * (decision_day - ledger$day))
  # Only numerical roundoff can be negative after ledger validation.
  max(0, kg_days) * storage_eur_per_kg_day
}

# Study helper: randomly assign distinct fruit to day-specific slots. Nested
# prefixes of each day's slots couple plans without inspecting any fruit twice.
# Latent lifetimes stay in the simulator; only the observed label leaves here.
plan_value_roster <- function(lifetimes, max_per_group = 180L, days = c(3L, 6L, 9L, 12L)) {
  assert_nonnegative_scalar(max_per_group, "max_per_group", integer = TRUE)
  if (max_per_group < 1L || !is.numeric(days) || !length(days) || any(!is.finite(days)) ||
      any(days <= 0 | days != floor(days)) || anyDuplicated(days) ||
      !is.list(lifetimes) || !length(lifetimes) || is.null(names(lifetimes)) ||
      anyNA(names(lifetimes)) || any(!nzchar(names(lifetimes))) || anyDuplicated(names(lifetimes))) {
    stop("roster needs named populations, positive sample counts and unique inspection days", call. = FALSE)
  }
  do.call(rbind, lapply(names(lifetimes), function(group) {
    times <- lifetimes[[group]]
    n <- max_per_group * length(days)
    if (!is.numeric(times) || length(times) < n || any(!is.finite(times)) || any(times < 0)) {
      stop("roster needs enough distinct fruit with finite nonnegative lifetimes", call. = FALSE)
    }
    ids <- sample.int(length(times), n, replace = FALSE)
    day <- rep(days, each = max_per_group)
    probability <- inspection_label_probability(as.numeric(times[ids] > day), 0.9, 0.9)
    data.frame(cohort = group, fruit_id = ids, day = day,
      slot = rep(seq_len(max_per_group), length(days)),
      reported_acceptable = stats::rbinom(n, 1L, probability))
  }))
}

# Internal conversion of a generated roster to the policy's aggregate observations.
plan_value_observations <- function(roster, per_group) {
  assert_nonnegative_scalar(per_group, "per_group", integer = TRUE)
  if (per_group < 1L || per_group > min(tapply(roster$slot, list(roster$cohort, roster$day), max))) {
    stop("requested plan exceeds the prepared sampling roster", call. = FALSE)
  }
  selected <- roster[roster$slot <= per_group, , drop = FALSE]
  inspections <- stats::aggregate(selected$reported_acceptable,
    list(cohort = selected$cohort, day = selected$day), sum)
  names(inspections)[3] <- "n_acceptable"
  inspections$n_checked <- per_group
  removals <- data.frame(cohort = inspections$cohort, day = inspections$day,
    mass_kg = 0.20 * inspections$n_checked)
  list(inspections = inspections, removals = removals, selected = selected)
}

# Public information boundary: no fruit IDs, latent lifetimes or true parameters.
fit_plan_value_policy <- function(inspections, inventory, prices, removals) {
  model <- fit_shape_ensemble(inspections, inventory, 12L, 0.9, 0.9)
  chosen <- optimal_ensemble_sale_after_removals(model, prices, removals, 0.001, 2L)
  list(sale_day = chosen$sale_day, weight_shared = unname(model$weights["shared"]))
}

# Score one preselected date on the actual, uninspected fruit. All returned values
# include holding from harvest; inspection labour is added in the cost summary.
score_plan_value <- function(lot, plan, policy) {
  remaining <- lot$truth
  remaining$mass_kg <- unname(inspection_remaining_mass(lot$truth, plan$removals, 12L))
  times <- lapply(names(lot$lifetimes), function(group) {
    removed <- plan$selected$fruit_id[plan$selected$cohort == group]
    lot$lifetimes[[group]][-removed]
  })
  names(times) <- names(lot$lifetimes)
  eligible <- remaining[remaining$initially_sellable, ]
  stopifnot(all(abs(eligible$mass_kg - 0.20 * lengths(times[eligible$cohort])) < 1e-8))
  past_cost <- predecision_holding_cost(lot$truth, plan$removals, 0.001, 12L)
  evaluate <- function(day) {
    realised_sale_value(day, remaining, lot$prices, times, 0.001, 12L, 2L) - past_cost
  }
  # No-inspection comparators retain every fruit and have no inspection expense.
  baseline <- function(day) realised_sale_value(day, lot$truth, lot$prices, lot$lifetimes,
                                                 0.001, 0L, 2L)
  chosen <- evaluate(policy$sale_day)
  same_plan_day12 <- evaluate(12L)
  no_inspection_day12 <- baseline(12L)
  data.frame(sale_day = policy$sale_day, weight_shared = policy$weight_shared,
    inspection_count = nrow(plan$selected), removed_eligible_kg = sum(plan$removals$mass_kg),
    remaining_eligible_kg = sum(eligible$mass_kg), predecision_storage_eur = past_cost,
    return_before_labour_eur = chosen, same_plan_day12_before_labour_eur = same_plan_day12,
    no_inspection_day12_eur = no_inspection_day12, no_inspection_day16_eur = baseline(16L),
    timing_gain_eur = chosen - same_plan_day12,
    removal_net_cost_eur = no_inspection_day12 - same_plan_day12)
}

#' Compare three destructive inspection plans with prespecified no-inspection sales.
#' @param n_lots Independent synthetic lots, at least two.
#' @param metadata_seed Seed for true lot parameters and hypothetical prices.
#' @param fruit_seed Seed for a finite population shared by all plans.
#' @param sampling_seed Seed for random sample IDs and reported-label errors.
#' @return One paired record per lot and plan; labour costs are applied in summaries.
run_plan_value_experiment <- function(n_lots = 200L, metadata_seed = 20261110L,
                                      fruit_seed = 20261111L, sampling_seed = 20261112L) {
  for (field in c("n_lots", "metadata_seed", "fruit_seed", "sampling_seed")) {
    assert_nonnegative_scalar(get(field), field, integer = TRUE)
  }
  if (n_lots < 2L) stop("at least two independent lots are required", call. = FALSE)
  set.seed(metadata_seed)
  lots <- lapply(seq_len(n_lots), function(id) {
    truth <- simulate_true_inventory()
    truth$mass_kg[1] <- 0.20 * round(truth$mass_kg[1] / 0.20)
    truth$mass_kg[2] <- 850 - truth$mass_kg[1]
    list(truth = truth, prices = simulate_price_scenario(12L, 28L))
  })
  set.seed(fruit_seed)
  for (id in seq_along(lots)) lots[[id]]$lifetimes <- simulate_fruit_lifetimes(lots[[id]]$truth)
  set.seed(sampling_seed)
  records <- lapply(seq_along(lots), function(id) {
    tryCatch({
      lot <- lots[[id]]
      roster <- plan_value_roster(lot$lifetimes)
      public_inventory <- transform(lot$truth, shape = 1, scale = 1)
      plans <- lapply(c(30L, 90L, 180L), function(budget) plan_value_observations(roster, budget))
      # Only observations through day 12 cross into fitting. All plans' decisions
      # are fixed before evaluating any sale on the hidden finite population.
      policies <- lapply(plans, function(plan) {
        fit_plan_value_policy(plan$inspections, public_inventory, lot$prices, plan$removals)
      })
      do.call(rbind, lapply(seq_along(plans), function(i) {
        cbind(data.frame(lot_id = id, per_group = c(30L, 90L, 180L)[i]),
          score_plan_value(lot, plans[[i]], policies[[i]]))
      }))
    }, error = function(error) {
      stop(sprintf("inspection-plan lot %d: %s", id, conditionMessage(error)), call. = FALSE)
    })
  })
  do.call(rbind, records)
}

validate_plan_value_records <- function(records) {
  fields <- c("lot_id", "per_group", "sale_day", "weight_shared", "inspection_count",
    "removed_eligible_kg", "remaining_eligible_kg", "predecision_storage_eur",
    "return_before_labour_eur", "same_plan_day12_before_labour_eur",
    "no_inspection_day12_eur", "no_inspection_day16_eur", "timing_gain_eur", "removal_net_cost_eur")
  if (!is.data.frame(records) || !nrow(records) || !all(fields %in% names(records)) ||
      any(!vapply(records[fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1))) ||
      any(records$lot_id <= 0 | records$lot_id != floor(records$lot_id)) ||
      length(unique(records$lot_id)) < 2L || !setequal(unique(records$per_group), c(30, 90, 180)) ||
      any(table(records$lot_id, records$per_group) != 1L)) {
    stop("records need complete finite pairs for all three plans on at least two lots", call. = FALSE)
  }
  if (any(records$inspection_count != 8 * records$per_group) ||
      any(abs(records$removed_eligible_kg - 0.20 * records$inspection_count) > 1e-8) ||
      any(abs(records$remaining_eligible_kg + records$removed_eligible_kg - 850) > 1e-8) ||
      any(abs(records$timing_gain_eur - records$return_before_labour_eur +
                records$same_plan_day12_before_labour_eur) > 1e-8) ||
      any(abs(records$removal_net_cost_eur - records$no_inspection_day12_eur +
                records$same_plan_day12_before_labour_eur) > 1e-8)) {
    stop("plan records violate inspection, mass or return accounting", call. = FALSE)
  }
  groups <- split(records, records$lot_id)
  for (field in c("no_inspection_day12_eur", "no_inspection_day16_eur")) {
    if (any(vapply(groups, function(x) length(unique(x[[field]])) != 1L, logical(1)))) {
      stop("plans must share each lot's no-inspection outcomes", call. = FALSE)
    }
  }
  invisible(TRUE)
}

#' Cost sensitivity with paired-lot intervals; no policy is retuned at any cost.
#' @param records Complete output of run_plan_value_experiment().
#' @param costs Distinct nonnegative labour charges in EUR per inspection.
#' @param n_boot Paired whole-lot resamples for marginal 95% intervals.
#' @return One row per plan/cost, including the break-even labour charge.
summarize_plan_value <- function(records, costs = c(0, 0.02, 0.05, 0.10), n_boot = 1000L) {
  validate_plan_value_records(records)
  if (!is.numeric(costs) || !length(costs) || any(!is.finite(costs)) || any(costs < 0) || anyDuplicated(costs)) {
    stop("costs must be distinct finite nonnegative charges", call. = FALSE)
  }
  result <- lapply(c(30L, 90L, 180L), function(budget) {
    part <- records[records$per_group == budget, ]
    part <- part[order(part$lot_id), ]
    count <- part$inspection_count[1]
    contrasts <- list(
      gain_vs_day12_eur = part$return_before_labour_eur - part$no_inspection_day12_eur,
      gain_vs_day16_eur = part$return_before_labour_eur - part$no_inspection_day16_eur,
      timing_gain_eur = part$timing_gain_eur, removal_net_cost_eur = part$removal_net_cost_eur)
    intervals <- lapply(contrasts, paired_lot_interval, n_boot = n_boot)
    do.call(rbind, lapply(sort(costs), function(cost) {
      row <- data.frame(per_group = budget, labour_eur_per_check = cost, n_lots = nrow(part),
        inspection_count = count, removed_eligible_kg = part$removed_eligible_kg[1],
        mean_sale_day = mean(part$sale_day), mean_predecision_storage_eur = mean(part$predecision_storage_eur),
        mean_return_before_labour_eur = mean(part$return_before_labour_eur),
        mean_labour_eur = cost * count, mean_net_return_eur = mean(part$return_before_labour_eur) - cost * count,
        mean_no_inspection_day12_eur = mean(part$no_inspection_day12_eur),
        mean_no_inspection_day16_eur = mean(part$no_inspection_day16_eur))
      for (contrast in names(intervals)) {
        interval <- intervals[[contrast]]
        if (startsWith(contrast, "gain_vs_")) interval <- interval - cost * count
        for (statistic in names(interval)) row[[paste0(contrast, "_", statistic)]] <- unname(interval[statistic])
      }
      for (statistic in names(intervals[[1]])) {
        row[[paste0("break_even_labour_vs_day12_", statistic)]] <- unname(intervals[[1]][statistic]) / count
      }
      net <- part$return_before_labour_eur - cost * count
      row$below_day12_fraction <- mean(net < part$no_inspection_day12_eur)
      row$below_day16_fraction <- mean(net < part$no_inspection_day16_eur)
      row
    }))
  })
  do.call(rbind, result)
}
