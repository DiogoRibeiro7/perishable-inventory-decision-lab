# Source model, sampling, evaluation, simulation, shared_shape,
# shared_shape_evaluation, shape_ensemble and inspection_removals first.

# Receives observed counts, inventory metadata, prices and the past removal ledger only.
fit_removal_policy <- function(inspections, inventory, prices, removals) {
  model <- fit_shape_ensemble(inspections, inventory, 12L, 0.9, 0.9)
  naive <- ensemble_value_grid(model, prices, 0.001, 2L)
  accounted <- ensemble_value_after_removals(model, prices, removals, 0.001, 2L)
  i <- which.max(naive$expected_net_eur)
  j <- which.max(accounted$expected_net_eur)
  list(sale_day_naive = naive$sale_day[i], sale_day_accounted = accounted$sale_day[j],
    fitted_naive_at_naive_day_eur = naive$expected_net_eur[i],
    fitted_accounted_at_naive_day_eur = accounted$expected_net_eur[i],
    fitted_accounted_at_accounted_day_eur = accounted$expected_net_eur[j],
    weight_shared = unname(model$weights["shared"]))
}

# Generate only the uninspected remainder, after every decision has been fixed.
removal_study_lifetimes <- function(remaining_inventory) {
  simulate_fruit_lifetimes(remaining_inventory, mean_fruit_kg = 0.20)
}

#' Compare inventory-unaware and removal-aware sale decisions on the same remainder.
#' @param n_lots Independent base lots, at least two.
#' @param training_seed Seed for lot parameters, prices and past inspection counts.
#' @param outcome_seed Separate seed for remaining fruit lifetimes, drawn after fitting.
#' @return One paired record per lot; realised returns include inspection labour cost.
run_removal_experiment <- function(n_lots = 200L, training_seed = 20261108L,
                                     outcome_seed = 20261109L) {
  for (field in c("n_lots", "training_seed", "outcome_seed")) {
    assert_nonnegative_scalar(get(field), field, integer = TRUE)
  }
  if (n_lots < 2L) stop("at least two independent lots are required", call. = FALSE)
  set.seed(training_seed)
  lots <- lapply(seq_len(n_lots), function(id) {
    tryCatch({
      truth <- simulate_true_inventory()
      # Exactly 4,250 eligible fruit, each weighing 0.20 kg.
      truth$mass_kg[1] <- 0.20 * round(truth$mass_kg[1] / 0.20)
      truth$mass_kg[2] <- 850 - truth$mass_kg[1]
      prices <- simulate_price_scenario(12L, 28L)
      inspections <- shape_study_inspections(truth, c(3L, 6L, 9L, 12L), 180L,
                                              stats::runif(8L), 0.9, 0.9)
      removals <- data.frame(cohort = inspections$cohort, day = inspections$day,
        mass_kg = 0.20 * inspections$n_checked)
      public_inventory <- transform(truth, shape = 1, scale = 1)
      policy <- fit_removal_policy(inspections, public_inventory, prices, removals)
      remaining <- truth
      remaining$mass_kg <- unname(inspection_remaining_mass(truth, removals, 12L))
      validate_cohorts(remaining)
      list(truth = truth, remaining = remaining, prices = prices, policy = policy,
        inspection_count = sum(inspections$n_checked))
    }, error = function(error) {
      stop(sprintf("destructive-inspection lot %d: %s", id, conditionMessage(error)), call. = FALSE)
    })
  })
  set.seed(outcome_seed)
  records <- lapply(seq_along(lots), function(id) {
    lot <- lots[[id]]
    lifetimes <- removal_study_lifetimes(lot$remaining)
    cost <- 0.02 * lot$inspection_count
    evaluate <- function(day) {
      realised_sale_value(day, lot$remaining, lot$prices, lifetimes, 0.001, 12L, 2L) - cost
    }
    true_grid <- expected_value_grid(lot$remaining, lot$prices, 0.001, 12L, 2L)
    expected <- function(day) true_grid$expected_net_eur[true_grid$sale_day == day] - cost
    row <- cbind(data.frame(lot_id = id), as.data.frame(lot$policy))
    row$initial_advanced_kg <- lot$truth$mass_kg[1]
    row$remaining_advanced_kg <- lot$remaining$mass_kg[1]
    row$remaining_eligible_kg <- sum(lot$remaining$mass_kg[lot$remaining$initially_sellable])
    row$removed_eligible_kg <- 850 - row$remaining_eligible_kg
    row$inspection_count <- lot$inspection_count
    row$inspection_cost_eur <- cost
    for (method in c("naive", "accounted", "immediate")) {
      day <- if (method == "immediate") 12L else lot$policy[[paste0("sale_day_", method)]]
      row[[paste0("realised_", method, "_eur")]] <- evaluate(day)
      row[[paste0("true_expected_", method, "_eur")]] <- expected(day)
    }
    row
  })
  do.call(rbind, records)
}

#' Summarise value-accounting differences and paired decision consequences.
#' @param records Output of run_removal_experiment().
#' @param n_boot Whole-lot resamples for marginal percentile intervals.
#' @return One-row summary of means, paired intervals and descriptive frequencies.
summarize_removal_experiment <- function(records, n_boot = 1000L) {
  fields <- c("lot_id", "sale_day_naive", "sale_day_accounted", "remaining_eligible_kg",
    "removed_eligible_kg", "inspection_cost_eur", "fitted_naive_at_naive_day_eur",
    "fitted_accounted_at_naive_day_eur", "fitted_accounted_at_accounted_day_eur",
    "realised_naive_eur", "realised_accounted_eur", "realised_immediate_eur",
    "true_expected_naive_eur", "true_expected_accounted_eur", "true_expected_immediate_eur")
  if (!is.data.frame(records) || nrow(records) < 2L || !all(fields %in% names(records)) ||
      any(!vapply(records[fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1))) ||
      anyDuplicated(records$lot_id)) {
    stop("records need finite paired measurements from at least two distinct lots", call. = FALSE)
  }
  row <- data.frame(n_lots = nrow(records))
  for (field in setdiff(fields, "lot_id")) row[[paste0("mean_", field)]] <- mean(records[[field]])
  differences <- list(
    fitted_value_difference_eur = records$fitted_naive_at_naive_day_eur - records$fitted_accounted_at_naive_day_eur,
    fitted_decision_gain_eur = records$fitted_accounted_at_accounted_day_eur - records$fitted_accounted_at_naive_day_eur,
    expected_return_gain_eur = records$true_expected_accounted_eur - records$true_expected_naive_eur,
    realised_return_gain_eur = records$realised_accounted_eur - records$realised_naive_eur,
    accounted_minus_immediate_eur = records$realised_accounted_eur - records$realised_immediate_eur)
  for (contrast in names(differences)) {
    interval <- paired_lot_interval(differences[[contrast]], n_boot)
    for (statistic in names(interval)) row[[paste0(contrast, "_", statistic)]] <- unname(interval[statistic])
  }
  row$different_sale_day_fraction <- mean(records$sale_day_accounted != records$sale_day_naive)
  row$accounted_below_naive_fraction <- mean(records$realised_accounted_eur < records$realised_naive_eur)
  row$accounted_below_immediate_fraction <- mean(records$realised_accounted_eur < records$realised_immediate_eur)
  row$naive_below_immediate_fraction <- mean(records$realised_naive_eur < records$realised_immediate_eur)
  row
}
