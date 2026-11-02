#' Paired, prospective simulations of maturity-aware selling decisions.
#'
#' Source model.R, sampling.R and evaluation.R first. Each generated lot has
#' independent latent survival parameters. Held-out inspections and realised
#' fruit lifetimes are never provided to the policies before their choices.

#' Generate a synthetic lot with heterogeneous maturity strata.
#' @return Initial inventory with inaccessible true survival parameters.
simulate_true_inventory <- function() {
  eligible_total <- 850
  advanced_mass <- eligible_total * stats::runif(1, 0.25, 0.60)
  data.frame(
    cohort = c("advanced", "intermediate", "initially_immature"),
    mass_kg = c(advanced_mass, eligible_total - advanced_mass, 150),
    initially_sellable = c(TRUE, TRUE, FALSE),
    shape = c(2.2 * exp(stats::rnorm(1, 0, 0.08)),
              1.8 * exp(stats::rnorm(1, 0, 0.08)), 1),
    scale = c(18 * exp(stats::rnorm(1, 0, 0.12)),
              36 * exp(stats::rnorm(1, 0, 0.12)), 1),
    stringsAsFactors = FALSE
  )
}

#' Draw independent cross-sectional inspections from a true survival model.
#' @param truth Synthetic initial inventory containing hidden survival curves.
#' @param days Positive whole-number inspection days.
#' @param per_group Count inspected in each maturity stratum and day.
#' @return Aggregate inspection data frame.
simulate_inspections <- function(truth, days, per_group = 180L) {
  validate_cohorts(truth)
  assert_nonnegative_scalar(per_group, "per_group", integer = TRUE)
  if (per_group < 1L || !is.numeric(days) || length(days) < 1L ||
      anyNA(days) || any(!is.finite(days)) ||
      any(days <= 0 | days != floor(days)) || anyDuplicated(days)) {
    stop("days must be unique positive whole days; per_group must be positive",
         call. = FALSE)
  }
  inspections <- expand.grid(
    cohort = truth$cohort[truth$initially_sellable], day = days,
    KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE
  )
  inspections$n_checked <- as.integer(per_group)
  match_index <- match(inspections$cohort, truth$cohort)
  probability <- weibull_survival(
    inspections$day, truth$shape[match_index], truth$scale[match_index]
  )
  inspections$n_acceptable <- stats::rbinom(
    nrow(inspections), size = inspections$n_checked, prob = probability
  )
  inspections
}

#' Create an exogenous, entirely hypothetical cohort-specific price scenario.
#' @param decision_day Current decision day.
#' @param horizon Last possible sale day, inclusive.
#' @return Complete price grid in EUR/kg.
simulate_price_scenario <- function(decision_day = 12L, horizon = 28L) {
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  assert_nonnegative_scalar(horizon, "horizon", integer = TRUE)
  if (horizon < decision_day) {
    stop("horizon must not precede decision_day", call. = FALSE)
  }
  price <- expand.grid(
    cohort = c("advanced", "intermediate"),
    day = seq.int(decision_day, horizon),
    KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE
  )
  common_slope <- stats::runif(1, -0.015, 0.085)
  slope <- c(advanced = common_slope * stats::runif(1, 0.8, 1.2),
             intermediate = common_slope * stats::runif(1, 0.8, 1.2))
  baseline <- c(advanced = 0.84, intermediate = 0.78)
  price$price_eur_per_kg <- baseline[price$cohort] +
    slope[price$cohort] * (price$day - decision_day)
  if (any(price$price_eur_per_kg < 0)) {
    stop("synthetic price scenario unexpectedly became negative",
         call. = FALSE)
  }
  price
}

#' Simulate fruit-level, paired potential postharvest failure times.
#'
#' Each fruit in a cohort has an equal synthetic mass. The same lifetimes are
#' used to score every policy, preventing independent outcome noise from
#' contaminating paired comparisons. This does not model shared storage shocks.
#'
#' @param truth Synthetic true cohort parameters.
#' @param mean_fruit_kg Assumed equal within-stratum fruit mass.
#' @return Named list of numeric failure times, one per eligible cohort.
simulate_fruit_lifetimes <- function(truth, mean_fruit_kg = 0.20) {
  validate_cohorts(truth)
  assert_nonnegative_scalar(mean_fruit_kg, "mean_fruit_kg")
  if (mean_fruit_kg == 0) {
    stop("mean_fruit_kg must be positive", call. = FALSE)
  }
  eligible <- truth[truth$initially_sellable, , drop = FALSE]
  lifetimes <- lapply(seq_len(nrow(eligible)), function(i) {
    n_fruits <- max(1L, as.integer(round(eligible$mass_kg[i] / mean_fruit_kg)))
    stats::rweibull(n_fruits, shape = eligible$shape[i],
                    scale = eligible$scale[i])
  })
  names(lifetimes) <- eligible$cohort
  lifetimes
}

#' Realised paired economic outcome for a policy's chosen selling day.
#'
#' @param sale_day Whole day selected using only information available earlier.
#' @param truth Initial cohort inventory; shape/scale are not used here.
#' @param prices Exogenous prices available when the policy was evaluated.
#' @param lifetimes Fixed latent fruit failure times shared across policies.
#' @param storage_eur_per_kg_day Marginal per-initial-kg storage cost.
#' @param decision_day First possible sale day.
#' @param delivery_lag_days Delay from sale until commercial acceptance.
#' @return Realised net EUR, inclusive of holding cost.
realised_sale_value <- function(sale_day, truth, prices, lifetimes,
                                storage_eur_per_kg_day, decision_day,
                                delivery_lag_days = 2L) {
  validate_cohorts(truth)
  validate_prices(prices, truth)
  assert_nonnegative_scalar(sale_day, "sale_day", integer = TRUE)
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  assert_nonnegative_scalar(delivery_lag_days, "delivery_lag_days",
                            integer = TRUE)
  assert_nonnegative_scalar(storage_eur_per_kg_day,
                            "storage_eur_per_kg_day")
  if (sale_day < decision_day || !(sale_day %in% prices$day)) {
    stop("sale_day must be an available future price day", call. = FALSE)
  }
  eligible <- truth[truth$initially_sellable, , drop = FALSE]
  if (!is.list(lifetimes) || !setequal(names(lifetimes), eligible$cohort)) {
    stop("lifetimes need exactly one vector per eligible cohort",
         call. = FALSE)
  }
  gross <- 0
  for (i in seq_len(nrow(eligible))) {
    group <- eligible$cohort[i]
    time_to_failure <- lifetimes[[group]]
    if (!is.numeric(time_to_failure) || length(time_to_failure) == 0L ||
        anyNA(time_to_failure) || any(!is.finite(time_to_failure)) ||
        any(time_to_failure < 0)) {
      stop("each cohort needs nonnegative, finite fruit lifetimes",
           call. = FALSE)
    }
    accepted_mass <- eligible$mass_kg[i] *
      mean(time_to_failure > sale_day + delivery_lag_days)
    quote <- prices$price_eur_per_kg[
      prices$cohort == group & prices$day == sale_day
    ]
    gross <- gross + accepted_mass * quote
  }
  storage_cost <- sum(eligible$mass_kg) * storage_eur_per_kg_day *
    (sale_day - decision_day + delivery_lag_days)
  gross - storage_cost
}

#' Prepare one prospective lot, fixing decisions before future outcomes.
#' @param lot_id Integer lot identifier.
#' @param decision_day Training cutoff and first possible sale day.
#' @param delivery_lag_days Lag until quality is assessed at delivery.
#' @param storage_eur_per_kg_day Per-initial-kg daily storage cost.
#' @param additional_policy Optional function with the same arguments as
#'   optimal_batch_sale(), returning one sale day. Receives fitted inventory
#'   and forecast prices only, before any held-out outcomes are generated.
#' @return List of fixed decisions, scores, inventory, prices and fruit outcomes.
simulate_policy_lot <- function(lot_id, decision_day = 12L,
                                delivery_lag_days = 2L,
                                storage_eur_per_kg_day = 0.001,
                                additional_policy = NULL) {
  assert_nonnegative_scalar(lot_id, "lot_id", integer = TRUE)
  assert_nonnegative_scalar(decision_day, "decision_day", integer = TRUE)
  if (decision_day < 4L) {
    stop("decision_day must allow at least three earlier inspection dates",
         call. = FALSE)
  }
  if (!is.null(additional_policy) && !is.function(additional_policy)) {
    stop("additional_policy must be NULL or a function", call. = FALSE)
  }
  truth <- simulate_true_inventory()
  inspection_days <- unique(as.integer(round(seq(3, decision_day, length.out = 4L))))
  if (length(inspection_days) < 3L) {
    stop("too few unique training inspection days", call. = FALSE)
  }
  train <- simulate_inspections(truth, inspection_days)
  fitted <- with_fitted_survival(truth, fit_weibull_by_cohort(train, truth))
  pooled <- with_pooled_survival(truth, fit_pooled_weibull(train, truth))
  prices <- simulate_price_scenario(decision_day, decision_day + 16L)

  # Only the pre-cutoff samples and assumed prices inform either policy.
  stratified_day <- optimal_batch_sale(
    fitted, prices, storage_eur_per_kg_day, decision_day, delivery_lag_days
  )$sale_day
  pooled_day <- optimal_batch_sale(
    pooled, prices, storage_eur_per_kg_day, decision_day, delivery_lag_days
  )$sale_day
  # The inaccessible true parameters define an expected-value oracle only.
  oracle_day <- optimal_batch_sale(
    truth, prices, storage_eur_per_kg_day, decision_day, delivery_lag_days
  )$sale_day
  additional_day <- NULL
  if (!is.null(additional_policy)) {
    additional_day <- additional_policy(
      fitted, prices, storage_eur_per_kg_day, decision_day, delivery_lag_days
    )
    assert_nonnegative_scalar(additional_day, "additional sale day", integer = TRUE)
    if (additional_day < decision_day || !(additional_day %in% prices$day)) {
      stop("additional policy must select an available future day", call. = FALSE)
    }
  }

  # Generate held-out assessments and common potential outcomes only AFTER
  # all selling dates have been determined.
  holdout <- simulate_inspections(truth,
                                  decision_day + c(4L, 8L, 12L), 250L)
  stratified_score <- score_future_inspections(holdout, fitted, decision_day)
  pooled_score <- score_future_inspections(holdout, pooled, decision_day)
  lifetimes <- simulate_fruit_lifetimes(truth)

  list(lot_id = lot_id, truth = truth, prices = prices, lifetimes = lifetimes,
       decision_day = decision_day, delivery_lag_days = delivery_lag_days,
       storage_eur_per_kg_day = storage_eur_per_kg_day,
       stratified_day = stratified_day, pooled_day = pooled_day,
       oracle_day = oracle_day, stratified_score = stratified_score,
       pooled_score = pooled_score, additional_day = additional_day,
       fitted_inventory = fitted, pooled_inventory = pooled)
}

#' Score fixed decisions on the same fruit under a supplied realised price path.
#' @param lot Prepared output of simulate_policy_lot().
#' @param realised_prices Prices used only for scoring, never to select a day.
#' @return One-row data frame. The oracle date retains its original forecast.
score_policy_lot <- function(lot, realised_prices = lot$prices) {
  evaluate_day <- function(day) {
    realised_sale_value(day, lot$truth, realised_prices, lot$lifetimes,
                        lot$storage_eur_per_kg_day, lot$decision_day,
                        lot$delivery_lag_days)
  }

  data.frame(
    lot_id = lot$lot_id,
    sale_day_stratified = lot$stratified_day,
    sale_day_pooled = lot$pooled_day,
    sale_day_oracle = lot$oracle_day,
    realised_stratified_eur = evaluate_day(lot$stratified_day),
    realised_pooled_eur = evaluate_day(lot$pooled_day),
    realised_immediate_eur = evaluate_day(lot$decision_day),
    realised_oracle_eur = evaluate_day(lot$oracle_day),
    brier_stratified = lot$stratified_score$brier,
    brier_pooled = lot$pooled_score$brier,
    log_loss_stratified = lot$stratified_score$log_loss,
    log_loss_pooled = lot$pooled_score$log_loss
  )
}

#' Run and score one lot with the original perfectly known price scenario.
#' @param lot_id Integer lot identifier.
#' @param decision_day Training cutoff and first possible sale day.
#' @param delivery_lag_days Lag until quality is assessed at delivery.
#' @param storage_eur_per_kg_day Per-initial-kg daily storage cost.
#' @return One-row data frame of future prediction and realised decision scores.
simulate_one_lot <- function(lot_id, decision_day = 12L,
                             delivery_lag_days = 2L,
                             storage_eur_per_kg_day = 0.001) {
  score_policy_lot(simulate_policy_lot(lot_id, decision_day, delivery_lag_days,
                                      storage_eur_per_kg_day))
}

#' Generate independent synthetic lots using an explicit reproducible seed.
#' @param n_lots Number of independent harvest-lot simulations, at least two.
#' @param seed Reproducible RNG seed. Resets the calling R session RNG.
#' @return One-row-per-lot results for paired policy evaluation.
run_policy_experiment <- function(n_lots = 100L, seed = 20261022L) {
  assert_nonnegative_scalar(n_lots, "n_lots", integer = TRUE)
  assert_nonnegative_scalar(seed, "seed", integer = TRUE)
  if (n_lots < 2L) {
    stop("at least two independent lots are required", call. = FALSE)
  }
  set.seed(seed)
  results <- lapply(seq_len(n_lots), function(lot_id) {
    tryCatch(simulate_one_lot(lot_id), error = function(error) {
      stop(sprintf("synthetic lot %d failed: %s", lot_id,
                   conditionMessage(error)), call. = FALSE)
    })
  })
  do.call(rbind, results)
}
