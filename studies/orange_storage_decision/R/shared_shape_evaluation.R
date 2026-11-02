# Source model, sampling, evaluation, simulation and shared_shape first.

default_shape_scenarios <- function() {
  data.frame(scenario = c("common_shape", "nearby_shapes", "different_shapes"),
    advanced_shape = c(2, 2.2, 1), intermediate_shape = c(2, 1.8, 3.5),
    common_jitter = c(TRUE, FALSE, FALSE))
}

validate_shape_scenarios <- function(scenarios) {
  if (!is.data.frame(scenarios) || nrow(scenarios) < 1L ||
      !all(c("scenario", "advanced_shape", "intermediate_shape", "common_jitter") %in% names(scenarios)) ||
      !is.character(scenarios$scenario) || anyNA(scenarios$scenario) ||
      any(!nzchar(trimws(scenarios$scenario))) || anyDuplicated(scenarios$scenario) ||
      !is.logical(scenarios$common_jitter) || anyNA(scenarios$common_jitter)) {
    stop("shape scenarios need unique names, shape centres and a common_jitter flag", call. = FALSE)
  }
  for (field in c("advanced_shape", "intermediate_shape")) {
    if (!is.numeric(scenarios[[field]]) || any(!is.finite(scenarios[[field]])) ||
        any(scenarios[[field]] <= 0)) stop("shape centres must be positive and finite", call. = FALSE)
  }
}

#' Draw paired binomial inspections by inverse CDF with supplied independent uniforms.
shape_study_inspections <- function(truth, days, per_group, uniforms, sensitivity = 1, specificity = 1) {
  validate_cohorts(truth)
  assert_nonnegative_scalar(per_group, "per_group", integer = TRUE)
  rows <- expand.grid(cohort = truth$cohort[truth$initially_sellable], day = days,
                       KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
  if (!is.numeric(uniforms) || length(uniforms) != nrow(rows) ||
      any(!is.finite(uniforms)) || any(uniforms <= 0 | uniforms >= 1)) {
    stop("one independent (0,1) uniform is required per inspection", call. = FALSE)
  }
  index <- match(rows$cohort, truth$cohort)
  q <- inspection_label_probability(weibull_survival(rows$day, truth$shape[index], truth$scale[index]),
                                     sensitivity, specificity)
  rows$n_checked <- per_group
  rows$n_acceptable <- stats::qbinom(uniforms, per_group, q)
  validate_inspection_counts(rows, truth)
  rows
}

#' Select a sale date using only past reported counts and known inspection rates.
fit_shape_policy <- function(inspections, inventory, prices, method,
                              sensitivity = 0.9, specificity = 0.9) {
  if (any(inspections$day > 12L)) stop("shape policy cannot use inspections after day 12", call. = FALSE)
  fitter <- switch(method, separate = fit_weibull_by_cohort, shared = fit_shared_shape_weibull,
                     stop("method must be separate or shared", call. = FALSE))
  fits <- fitter(inspections, inventory, sensitivity, specificity)
  fitted <- with_fitted_survival(inventory, fits)
  list(inventory = fitted, fits = fits,
       sale_day = optimal_batch_sale(fitted, prices, 0.001, 12L, 2L)$sale_day)
}

# Generate future uniforms only after every fit and decision has been fixed.
shape_study_outcome_uniforms <- function(inventory) {
  eligible <- inventory[inventory$initially_sellable, ]
  lifetimes <- lapply(eligible$mass_kg, function(mass) stats::runif(max(1L, as.integer(round(mass / 0.20)))))
  names(lifetimes) <- eligible$cohort
  list(holdout = stats::runif(3L * nrow(eligible)), lifetimes = lifetimes)
}

#' Compare separate and shared-shape fits on paired, independently generated lots.
#' @param n_lots Independent lots, at least two, in each prespecified scenario.
#' @param training_seed Seed for inventory, forecast and reported training uniforms.
#' @param outcome_seed Separate seed for future gold-standard inspections and fruit.
#' @param scenarios Generating shape centres and shared/independent log-scale jitter.
#' @param additional_policy Optional builder receiving past inspections, public inventory,
#'   prices and fitted policies. Returns sale_day, predict(cohort, day), and optional
#'   named numeric diagnostics. It never receives generating truth or future outcomes.
#' @param policy_fitter Component fitter using only past counts, public inventory,
#'   prices and method. Defaults to the original separate/shared fits.
#' @param training_per_group Positive inspection count per stratum and training day.
#' @return One row per lot/scenario. Rates Se=Sp=0.9 are known to both fits.
run_shared_shape_experiment <- function(n_lots = 200L, training_seed = 20261102L,
                                        outcome_seed = 20261103L,
                                        scenarios = default_shape_scenarios(),
                                        additional_policy = NULL,
                                        policy_fitter = fit_shape_policy,
                                        training_per_group = 180L) {
  validate_shape_scenarios(scenarios)
  if (!is.function(policy_fitter)) stop("policy_fitter must be a function", call. = FALSE)
  if (!is.null(additional_policy) && !is.function(additional_policy)) {
    stop("additional_policy must be NULL or a function", call. = FALSE)
  }
  for (field in c("n_lots", "training_seed", "outcome_seed", "training_per_group")) {
    assert_nonnegative_scalar(get(field), field, integer = TRUE)
  }
  if (n_lots < 2L) stop("at least two independent lots are required", call. = FALSE)
  if (training_per_group < 1L) stop("training_per_group must be positive", call. = FALSE)
  set.seed(training_seed)
  lots <- lapply(seq_len(n_lots), function(id) {
    base <- simulate_true_inventory()
    prices <- simulate_price_scenario(12L, 28L)
    uniforms <- stats::runif(8L)
    jitter <- base$shape[1:2] / c(2.2, 1.8)
    public_inventory <- transform(base, shape = 1, scale = 1)
    cases <- lapply(seq_len(nrow(scenarios)), function(i) {
      tryCatch({
        setting <- scenarios[i, ]
        noise <- if (setting$common_jitter) rep(sqrt(prod(jitter)), 2) else jitter
        truth <- base
        truth$shape[1:2] <- c(setting$advanced_shape, setting$intermediate_shape) * noise
        train <- shape_study_inspections(truth, c(3L, 6L, 9L, 12L), training_per_group,
                                         uniforms, 0.9, 0.9)
        policies <- lapply(c("separate", "shared"), function(method) {
          policy_fitter(train, public_inventory, prices, method)
        })
        names(policies) <- c("separate", "shared")
        additional <- NULL
        if (!is.null(additional_policy)) {
          additional <- additional_policy(train, public_inventory, prices, policies)
          if (!is.list(additional) || !is.function(additional$predict)) {
            stop("additional policy needs a sale day and prediction function", call. = FALSE)
          }
          assert_nonnegative_scalar(additional$sale_day, "additional sale day", integer = TRUE)
          if (!(additional$sale_day %in% 12:28)) stop("additional sale day must be in 12:28", call. = FALSE)
          diagnostics <- additional$diagnostics
          if (!is.null(diagnostics) && (!is.numeric(diagnostics) || any(!is.finite(diagnostics)) ||
              is.null(names(diagnostics)) || anyNA(names(diagnostics)) ||
              any(!nzchar(names(diagnostics))) || anyDuplicated(names(diagnostics)))) {
            stop("additional diagnostics must be finite with unique names", call. = FALSE)
          }
        }
        list(truth = truth, policies = policies, additional = additional)
      }, error = function(error) {
        stop(sprintf("lot %d, %s: %s", id, scenarios$scenario[i], conditionMessage(error)), call. = FALSE)
      })
    })
    list(prices = prices, inventory = public_inventory, cases = cases)
  })
  set.seed(outcome_seed)
  records <- lapply(seq_along(lots), function(id) {
    lot <- lots[[id]]
    uniforms <- shape_study_outcome_uniforms(lot$inventory)
    do.call(rbind, lapply(seq_len(nrow(scenarios)), function(i) {
      case <- lot$cases[[i]]
      truth <- case$truth
      holdout <- shape_study_inspections(truth, c(16L, 20L, 24L), 250L, uniforms$holdout)
      lifetimes <- lapply(names(uniforms$lifetimes), function(group) {
        j <- match(group, truth$cohort)
        stats::qweibull(uniforms$lifetimes[[group]], truth$shape[j], truth$scale[j])
      })
      names(lifetimes) <- names(uniforms$lifetimes)
      evaluate <- function(day) realised_sale_value(day, truth, lot$prices, lifetimes, 0.001, 12L, 2L)
      row <- data.frame(lot_id = id, scenario = scenarios$scenario[i],
        true_shape_advanced = truth$shape[1], true_shape_intermediate = truth$shape[2],
        realised_immediate_eur = evaluate(12L))
      for (method in c("separate", "shared")) {
        policy <- case$policies[[method]]
        scores <- score_future_inspections(holdout, policy$inventory, 12L)
        row[[paste0("sale_day_", method)]] <- policy$sale_day
        row[[paste0("realised_", method, "_eur")]] <- evaluate(policy$sale_day)
        row[[paste0("brier_", method)]] <- scores$brier
        row[[paste0("log_loss_", method)]] <- scores$log_loss
        for (group in c("advanced", "intermediate")) {
          j <- match(group, policy$inventory$cohort)
          row[[paste0("shape_", method, "_", group)]] <- policy$inventory$shape[j]
        }
      }
      if (!is.null(case$additional)) {
        policy <- case$additional
        scores <- score_future_probabilities(holdout, lot$inventory,
          policy$predict(holdout$cohort, holdout$day), 12L)
        row$sale_day_additional <- policy$sale_day
        row$realised_additional_eur <- evaluate(policy$sale_day)
        row$brier_additional <- scores$brier
        row$log_loss_additional <- scores$log_loss
        for (name in names(policy$diagnostics)) row[[paste0("additional_", name)]] <- policy$diagnostics[[name]]
      }
      row
    }))
  })
  result <- do.call(rbind, records)
  rownames(result) <- NULL
  result
}

#' Paired mean prediction/return contrasts with marginal whole-lot bootstrap intervals.
summarize_shared_shape <- function(records, n_boot = 1000L) {
  fields <- c("lot_id", "realised_immediate_eur", "sale_day_separate", "sale_day_shared",
    "realised_separate_eur", "realised_shared_eur", "brier_separate", "brier_shared",
    "log_loss_separate", "log_loss_shared")
  if (!is.data.frame(records) || !all(c("scenario", fields) %in% names(records)) ||
      !is.character(records$scenario) || anyNA(records$scenario) ||
      any(!nzchar(trimws(records$scenario))) ||
      any(!vapply(records[fields], function(x) is.numeric(x) && all(is.finite(x)), logical(1))) ||
      anyDuplicated(records[c("lot_id", "scenario")]) || length(unique(records$lot_id)) < 2L ||
      any(table(records$scenario) != length(unique(records$lot_id)))) {
    stop("records need complete, finite, paired lot/scenario measurements", call. = FALSE)
  }
  do.call(rbind, lapply(unique(records$scenario), function(scenario) {
    part <- records[records$scenario == scenario, ]
    row <- data.frame(scenario = scenario, n_lots = nrow(part))
    for (field in setdiff(fields, "lot_id")) row[[paste0("mean_", field)]] <- mean(part[[field]])
    differences <- list(brier_improvement = part$brier_separate - part$brier_shared,
      log_loss_improvement = part$log_loss_separate - part$log_loss_shared,
      shared_minus_separate_eur = part$realised_shared_eur - part$realised_separate_eur,
      shared_minus_immediate_eur = part$realised_shared_eur - part$realised_immediate_eur)
    for (contrast in names(differences)) {
      interval <- paired_lot_interval(differences[[contrast]], n_boot)
      for (statistic in names(interval)) row[[paste0(contrast, "_", statistic)]] <- unname(interval[statistic])
    }
    row$shared_below_immediate_fraction <- mean(part$realised_shared_eur < part$realised_immediate_eur)
    row$separate_below_immediate_fraction <- mean(part$realised_separate_eur < part$realised_immediate_eur)
    row$different_sale_day_fraction <- mean(part$sale_day_shared != part$sale_day_separate)
    row
  }))
}
