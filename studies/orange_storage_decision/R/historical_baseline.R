# Source model.R and sampling.R first. Base R only.

whole_calendar_day <- function(value, name) {
  if (!is.numeric(value) || length(value) != 1L || !is.finite(value) || value != floor(value)) {
    stop(sprintf("%s must be a finite whole calendar day", name), call. = FALSE)
  }
  invisible(TRUE)
}

#' Fit fixed stratum curves from completed historical lots only.
#' @param history Counts with lot_id, harvest_day, cohort, day, n_checked, n_acceptable.
#'   day is fruit age; harvest_day + day is the observation's calendar day.
#' @param inventory Initial stratum metadata; survival parameters are placeholders.
#' @param fit_calendar_day Last date on which training observations can be available.
#' @param sensitivity Known grading sensitivity, common to history and deployment.
#' @param specificity Known grading specificity, common to history and deployment.
#' @return Frozen working marginal Weibull fits and training provenance.
fit_historical_survival <- function(history, inventory, fit_calendar_day = 0L,
                                     sensitivity = 1, specificity = 1) {
  validate_cohorts(inventory)
  whole_calendar_day(fit_calendar_day, "fit_calendar_day")
  required <- c("lot_id", "harvest_day", "cohort", "day", "n_checked", "n_acceptable")
  if (!is.data.frame(history) || !nrow(history) || !all(required %in% names(history)) ||
      !is.character(history$lot_id) || anyNA(history$lot_id) || any(!nzchar(trimws(history$lot_id))) ||
      length(unique(history$lot_id)) < 2L || !is.numeric(history$harvest_day) ||
      any(!is.finite(history$harvest_day)) || any(history$harvest_day != floor(history$harvest_day))) {
    stop("history needs counts from at least two identified lots with whole harvest dates", call. = FALSE)
  }
  for (part in split(history, history$lot_id)) {
    validate_inspection_counts(part, inventory)
    if (length(unique(part$harvest_day)) != 1L || any(part$harvest_day + part$day > fit_calendar_day)) {
      stop("each historical lot needs one harvest date and no post-fit observations", call. = FALSE)
    }
  }
  # Equal-sized historical plans give equal lot weight at each stratum/day.
  # Unequal plans instead weight observations by their checked-fruit counts.
  counts <- stats::aggregate(history[c("n_checked", "n_acceptable")],
    list(cohort = history$cohort, day = history$day), sum)
  fits <- fit_weibull_by_cohort(counts, inventory, sensitivity, specificity)
  list(fits = fits, training_lot_ids = sort(unique(history$lot_id)), counts = counts,
    fit_calendar_day = fit_calendar_day, sensitivity = sensitivity, specificity = specificity,
    n_training_checks = sum(history$n_checked))
}

#' Apply a frozen historical model to an unseen lot at a valid decision date.
#' @param model Output of fit_historical_survival().
#' @param lot_id Unseen target lot identifier; training IDs are rejected.
#' @param inventory Target lot's initial inventory metadata.
#' @param harvest_day Target harvest calendar day.
#' @param decision_day Nonnegative whole age of the target lot at decision time.
#' @return Target inventory with the frozen historical curves, without refitting.
historical_fitted_inventory <- function(model, lot_id, inventory, harvest_day, decision_day) {
  whole_calendar_day(harvest_day, "harvest_day")
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  if (!is.list(model) || !all(c("fits", "training_lot_ids", "fit_calendar_day") %in% names(model)) ||
      !is.character(model$training_lot_ids) || !length(model$training_lot_ids) ||
      anyNA(model$training_lot_ids) || !is.character(lot_id) || length(lot_id) != 1L ||
      is.na(lot_id) || !nzchar(trimws(lot_id)) || lot_id %in% model$training_lot_ids) {
    stop("historical prediction needs a frozen model and an unseen target lot ID", call. = FALSE)
  }
  whole_calendar_day(model$fit_calendar_day, "model fit_calendar_day")
  if (model$fit_calendar_day > harvest_day + decision_day) {
    stop("historical model was fitted after the target decision date", call. = FALSE)
  }
  with_fitted_survival(inventory, model$fits)
}

#' Select a sale date using historical curves and the target lot's metadata only.
historical_sale_decision <- function(model, lot_id, inventory, prices, harvest_day,
                                      decision_day = 12L, storage_eur_per_kg_day = 0.001,
                                      delivery_lag_days = 2L) {
  fitted <- historical_fitted_inventory(model, lot_id, inventory, harvest_day, decision_day)
  optimal_batch_sale(fitted, prices, storage_eur_per_kg_day, decision_day, delivery_lag_days)
}
