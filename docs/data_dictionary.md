# Data dictionary

Three tables in `data/processed/`, all UTF-8 CSV. Money is nominal US dollars, in billions, not
adjusted for inflation.

## `billionaires.csv` — one row per person (5,535 rows)

| Column | Meaning |
|---|---|
| `person_id` | Forbes profile slug (e.g. `elon-musk`). People found only on the 1996/2001/2014 lists get `piie-<name>`. |
| `name` | Name as Forbes writes it today, or as on the historical list. |
| `gender` | `male` / `female`. |
| `birth_year` | From the Forbes profile; otherwise estimated as list year minus stated age. |
| `country`, `country_code` | Citizenship. ISO 3166 alpha-2 code where Forbes gives one. |
| `industry` | Forbes' 18-industry taxonomy. Historical-only people are mapped from the PIIE codes. |
| `source_of_wealth` | Company or asset Forbes names as the source of the fortune. |
| `organization`, `title` | Current role, when Forbes records one. |
| `wealth_origin` | `self-made`, `inherited, growing` (inherited and substantially grown) or `inherited`. Forbes' coding; PIIE's for historical-only people. |
| `self_made_score` | Forbes' 1-10 self-made score (10 = rags to riches), known for about one in seven people. |
| `piie_route` | PIIE's route to wealth: `founder non-finance`, `self-made finance`, `privatized and resources`, `executive`, `inherited`. Historical lists only. |
| `piie_inheritance` | PIIE's inheritance detail: `not inherited`, `father`, `3rd generation`, ..., `spouse/widow`. |
| `education_level` | Highest stated degree: `doctorate`, `master`, `bachelor`, `diploma or below`, `dropout`, `other`, `unknown`. |
| `dropout` | True if any listed degree is "Drop Out". |
| `schools` | Schools, `; `-separated. |
| `first_seen_year` | Earliest year the person is on any list we hold. **An upper bound** on the year they became a billionaire. |
| `first_seen_exact` | True when the first appearance falls inside continuous monthly data (after 2019-11-07) and the person is on no historical list. Only these rows are used for age-at-entry. |
| `age_at_first_seen` | `first_seen_year - birth_year`. |
| `company_founded` | Founding year of the main company (PIIE, historical lists only). |
| `years_from_founding` | `first_seen_year - company_founded`. |
| `historical_lists` | Which of 1996, 2001, 2014 the person appears on. |
| `rtb_first_seen`, `rtb_last_seen` | First and last monthly list (2019-11-07 to 2026-11-08) the person is on. |
| `months_listed` | Number of monthly lists (out of 84) the person is on. |
| `on_latest_list` | On the 2026-11-08 list. |
| `deceased` | Forbes' flag. |
| `net_worth_latest_bn`, `rank_latest` | On the last list the person appears on. |
| `net_worth_peak_bn` | Highest monthly value 2019-2026. |
| `linked_across_sources` | True if the historical record was matched to a Forbes profile. |
| `link_method` | `full` (every name token agrees) or `short` (first and last token agree, both unambiguous). |

## `net_worth_annual.csv` — one row per person per year, 2019-2026 (23,556 rows)

| Column | Meaning |
|---|---|
| `person_id`, `year` | Key. |
| `net_worth_year_end_bn` | Value on the last monthly list of the year the person is on. |
| `rank_year_end` | Rank on that list. |
| `net_worth_year_max_bn` | Highest monthly value that year. |
| `months_listed` | Monthly lists that year with the person on them. |
| `last_list_date` | Date of the list used for the year-end value. 2019 has one list (Nov 7); 2026 runs to Nov 8. |

## `historical_lists.csv` — the 1996, 2001 and 2014 lists (2,614 rows)

The PIIE-annotated Forbes lists, one row per list entry, with `person_id` added. Columns follow the
CORGIS release (`route`, `inheritance`, `piie_industry`, `company`, `company_founded`,
`relationship`). Unknown ages, coded as 0 or negative in the source, are blank.

## Known limitations

* **Name linkage.** The sources share no ID. 81% of the 2014 list is linked to a Forbes profile;
  older lists link less often mostly because their members have died or dropped off. Linking is
  deliberately conservative (an ambiguous name is never linked), so a missed link splits one
  person into two rows rather than merging two people.
* **Duplicate profiles.** Forbes sometimes re-files a person under a new slug. Pairs with the same
  normalised name and birth year that never appear on the same list are merged (294 profiles merged).
  A few duplicates whose names differ (e.g. an added surname) remain.
* **Families.** Some fortunes are listed as "X & family". They count as one person.
* **Censoring.** Nobody is observed before 1996, and there are no lists between 2001 and 2014 or
  between 2014 and November 2019.
