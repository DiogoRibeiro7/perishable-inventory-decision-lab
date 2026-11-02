# Run from studies/orange_storage_decision:
# Rscript scripts/run_adaptive_policy.R [number_of_lots] [output_directory]
source("R/model.R")
source("R/sampling.R")
source("R/simulation.R")
source("R/adaptive_policy.R")
source("R/adaptive_evaluation.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 2L) {
  stop("usage: run_adaptive_policy.R [number_of_lots] [output_directory]")
}
n_lots <- if (length(args)) suppressWarnings(as.numeric(args[1])) else 200L
destination <- if (length(args) == 2L) args[2] else "results/adaptive_policy"
settings <- list(n_lots = n_lots, seed = 20261101L, bootstrap_seed = 20261102L,
                 bootstrap_replicates = 1000L, prior = c(short = 0.3, typical = 0.4,
                                                         long = 0.3),
                 scenario_scale_multipliers = c(short = 0.70, typical = 1,
                                                long = 1.35),
                 prior_inspection_days = c(6L, 12L),
                 prior_checks_per_cohort_day = 6L, decision_day = 12L,
                 followup_inspection_day = 16L, checks_per_cohort = 8L,
                 eur_per_check = 0.02, delivery_lag_days = 2L,
                 storage_eur_per_kg_day = 0.001, r_version = R.version.string)
records <- run_adaptive_experiment(n_lots, seed = settings$seed,
                                   eur_per_check = settings$eur_per_check,
                                   checks_per_cohort = settings$checks_per_cohort)
set.seed(settings$bootstrap_seed)
summary <- summarize_adaptive_experiment(records, settings$bootstrap_replicates)

dir.create(destination, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(records, file.path(destination, "records.csv"), row.names = FALSE)
utils::write.csv(summary, file.path(destination, "summary.csv"), row.names = FALSE)
writeLines(trimws(capture.output(dput(settings)), which = "right"),
           file.path(destination, "settings.R"), useBytes = TRUE)

lines <- c("# Adaptive inspection: paired synthetic experiment", "",
  sprintf("%d independent lots from a known, three-point shelf-life prior.", n_lots),
  "Day-12 observations update the prior; a day-12 decision either commits to a",
  "fixed sale date or orders a nondestructive day-16 inspection. If inspected,",
  "day-16 observations update the posterior before choosing a sale date.",
  "Every alternative shares its lot, future price path, latent lifetimes and",
  "(where applicable) day-16 potential observations. The fixed policy never",
  "sees day-16 counts. Inspection labour is paid only if inspection occurs.", "",
  sprintf("Adaptive policy inspected %.1f%% of lots; mean planned net VOI EUR %+.2f.",
          100 * mean(records$action == "inspect"),
          mean(records$net_information_value_eur)), "",
  "| Paired comparison | Mean gain EUR [95% lot-bootstrap CI] | Below comparator |",
  "|---|---:|---:|")
for (i in seq_len(nrow(summary))) {
  x <- summary[i, ]
  lines <- c(lines, sprintf("| %s | %+.2f [%+.2f, %+.2f] | %.1f%% |",
    gsub("_", " ", x$comparison), x$mean_gain_eur,
    x$lower_95_eur, x$upper_95_eur,
    100 * x$fraction_below_baseline))
}
lines <- c(lines, "", "## Interpretation", "",
  "The policy is optimal only within the declared finite-scenario, perfect-label,",
  "independent-binomial model. The shelf-life prior is perfectly specified in",
  "this experiment; it is not learned from real market or biological records.",
  "The nonadaptive policy commits to its best date on day 12. The always-inspect",
  "policy buys day-16 information regardless of its prospective value.",
  "Price paths are assumed available and deterministic, so this is not a joint",
  "price-learning experiment. Earlier inspections and future follow-up samples",
  "are assumed nondestructive and do not change stock mass or create hidden",
  "handling damage. Labour for earlier inspections is identical across policies",
  "and excluded from all paired differences. Costs and returns start at day 12.",
  "95% percentile intervals resample whole lots; negative realised gains are",
  "retained. No empirical improvement is claimed.", "",
  sprintf("Reproduce with `Rscript scripts/run_adaptive_policy.R %d`.", n_lots),
  "See [design](../../ADAPTIVE_POLICY.md), [records](records.csv),",
  "[summary](summary.csv) and [settings](settings.R).")
writeLines(lines, file.path(destination, "RESULTS.md"), useBytes = TRUE)
cat(sprintf("Wrote %d adaptive-policy records to %s\n", nrow(records), destination))
print(summary, row.names = FALSE)
