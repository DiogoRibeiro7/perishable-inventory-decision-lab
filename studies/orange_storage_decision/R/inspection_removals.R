# Source model.R first; ensemble functions also require shape_ensemble.R.

#' Remaining physical mass after observed, nonselective removals by the cutoff.
#' @param inventory Initial inventory with fitted survival parameters.
#' @param removals Ledger with unique cohort/day rows and positive mass_kg removed.
#'   An empty ledger is valid. All removed fruit must be randomly selected within
#'   its stratum, irrespective of acceptable status; this is not quality-based culling.
#' @param decision_day Last observable removal day, a nonnegative whole day.
#' @return Named nonnegative mass vector in inventory row order, including zeros.
inspection_remaining_mass <- function(inventory, removals, decision_day) {
  validate_cohorts(inventory)
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  fields <- c("cohort", "day", "mass_kg")
  if (!is.data.frame(removals) || !all(fields %in% names(removals)) ||
      !is.character(removals$cohort) || anyNA(removals$cohort) ||
      any(!removals$cohort %in% inventory$cohort) || anyDuplicated(removals[c("cohort", "day")]) ||
      !is.numeric(removals$day) || any(!is.finite(removals$day)) ||
      any(removals$day < 0 | removals$day != floor(removals$day) | removals$day > decision_day) ||
      !is.numeric(removals$mass_kg) || any(!is.finite(removals$mass_kg)) || any(removals$mass_kg <= 0)) {
    stop("removals need unique known cohort/day rows, positive mass and no future observations", call. = FALSE)
  }
  removed <- vapply(inventory$cohort, function(group) sum(removals$mass_kg[removals$cohort == group]), numeric(1))
  # Permit only floating-point roundoff at a fully depleted boundary.
  tolerance <- 8 * .Machine$double.eps * pmax(1, inventory$mass_kg)
  if (any(removed > inventory$mass_kg + tolerance)) {
    stop("removed mass exceeds initial inventory", call. = FALSE)
  }
  remaining <- inventory$mass_kg - removed
  remaining[abs(remaining) <= tolerance] <- 0
  stats::setNames(remaining, inventory$cohort)
}

#' Value sale dates using mass still present after random destructive inspections.
#' @param inventory Initial inventory with fitted survival curves.
#' @param prices Prices agreed on sale day; complete for initially eligible strata.
#' @param removals Observed removal ledger passed to inspection_remaining_mass().
#' @param storage_eur_per_kg_day Holding cost per remaining eligible kilogram/day.
#' @param decision_day First candidate sale date and information cutoff.
#' @param delivery_lag_days Days from sale to quality assessment.
#' @return Expected-value grid; fully depleted strata contribute neither sales nor holding cost.
value_after_removals <- function(inventory, prices, removals, storage_eur_per_kg_day,
                                  decision_day = 0L, delivery_lag_days = 0L) {
  original <- expected_value_grid(inventory, prices, storage_eur_per_kg_day, decision_day, delivery_lag_days)
  remaining <- inspection_remaining_mass(inventory, removals, decision_day)
  if (!any(remaining[inventory$initially_sellable] > 0)) {
    for (field in c("expected_sellable_kg", "expected_gross_eur", "additional_storage_eur", "expected_net_eur")) {
      original[[field]] <- 0
    }
    return(original)
  }
  updated <- inventory
  updated$mass_kg <- unname(remaining)
  updated <- updated[updated$mass_kg > 0, , drop = FALSE]
  eligible <- updated$cohort[updated$initially_sellable]
  expected_value_grid(updated, prices[prices$cohort %in% eligible, ], storage_eur_per_kg_day,
                       decision_day, delivery_lag_days)
}

#' Earliest maximum-value sale date after observed removals.
optimal_sale_after_removals <- function(...) {
  grid <- value_after_removals(...)
  grid[which.max(grid$expected_net_eur), , drop = FALSE]
}

#' Apply an observed removal ledger to both fixed components of a survival mixture.
#' @param model Output of fit_shape_ensemble(); weights and survival curves stay fixed.
#' @param prices Complete price grid for the original inventory.
#' @param removals Observed removal ledger, containing no post-cutoff rows.
#' @param storage_eur_per_kg_day Holding cost per remaining eligible kilogram/day.
#' @param delivery_lag_days Days from sale to quality assessment.
#' @return Mixture expected values for the remaining physical inventory.
ensemble_value_after_removals <- function(model, prices, removals,
                                           storage_eur_per_kg_day, delivery_lag_days = 0L) {
  validate_shape_ensemble(model)
  grids <- lapply(model$inventories, function(inventory) {
    value_after_removals(inventory, prices, removals, storage_eur_per_kg_day,
                          model$decision_day, delivery_lag_days)
  })
  result <- grids[[1]]
  for (field in c("expected_sellable_kg", "expected_gross_eur", "additional_storage_eur", "expected_net_eur")) {
    result[[field]] <- model$weights[1] * grids[[1]][[field]] + model$weights[2] * grids[[2]][[field]]
  }
  result
}

#' Earliest maximum of the mixture value curve after removals.
optimal_ensemble_sale_after_removals <- function(...) {
  grid <- ensemble_value_after_removals(...)
  grid[which.max(grid$expected_net_eur), , drop = FALSE]
}
