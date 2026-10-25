"""Shared pandemic context, not a claim that all travel was prohibited."""

import html

GOODS_COVID_CONTEXT = {
    "start_year": 2020, "end_year": 2022,
    "measures": ["goods"],
    "label": "COVID-19 period, 2020-22",
    "note": "Shading marks 2020-2022 as COVID-19 context for goods trade. "
            "It does not indicate a suspension of goods trade or estimate the pandemic's causal effect.",
    "sources": [],
}

COVID_CONTEXT = {
    "start_year": 2020, "end_year": 2022,
    "measures": ["enrolled_students", "degree_students", "international_students", "study_abroad",
                 "visitors", "air_visitors", "leisure_visitors"],
    "label": "COVID travel restrictions, 2020-22",
    "note": "Shading marks 2020-2022, the main COVID travel-restriction years, not a universal travel ban. "
            "Rules, exemptions and reopening dates differed by destination; some measures continued into 2023. "
            "This is travel context, not a restriction on goods trade or a causal estimate.",
    "sources": [
        {"name": "U.S. country-specific entry restrictions ended November 8, 2021",
         "url": "https://www.govinfo.gov/content/pkg/FR-2021-10-28/html/2021-23645.htm"},
        {"name": "Mainland foreign-national visa-entry suspension began March 28, 2020",
         "url": "https://www.fmprc.gov.cn/wjbxw_new/202201/t20220113_10491272.shtml"},
        {"name": "Mainland quarantine and entry measures changed January 8, 2023",
         "url": "https://www.fmprc.gov.cn/wjbxw_new/202212/t20221227_10995607.shtml"},
        {"name": "Mainland visa issuance and validity restored March 15, 2023",
         "url": "https://english.beijing.gov.cn/latest/news/202303/t20230315_2936585.html"},
        {"name": "Hong Kong overseas nonresident restriction: March 25, 2020-May 1, 2022",
         "url": "https://www.info.gov.hk/gia/general/202204/22/P2022042200621.htm"},
        {"name": "Macau foreign-visitor restriction: March 18, 2020-August 31, 2022, with exemptions",
         "url": "https://www.dsec.gov.mo/getAttachment/0EC2B7EC-41BE-4615-B3FE-79307DE735AA/E_BME_PUB_2024_M10.aspx"},
    ],
    "measure_contexts": {"goods": GOODS_COVID_CONTEXT},
}


def context_for(measure):
    return COVID_CONTEXT["measure_contexts"].get(measure) or (
        COVID_CONTEXT if measure in COVID_CONTEXT["measures"] else None)


def applies_to(measure):
    return context_for(measure) is not None


def overlaps(first, last):
    return first <= COVID_CONTEXT["end_year"] and last >= COVID_CONTEXT["start_year"]


def svg_band(first, last, left, right, top, bottom, columns=False, domain=None, measure=None):
    context = context_for(measure) if measure is not None else COVID_CONTEXT
    if context is None or not overlaps(first, last):
        return ""
    low, high = domain or ((first - .5, last + .5) if columns else (first, max(first + 1, last)))
    start, end = max(low, 2019.5), min(high, 2022.5)
    if end <= start:
        return ""
    x1 = left + (start - low) / (high - low) * (right - left)
    x2 = left + (end - low) / (high - low) * (right - left)
    centre = max(left + 100, min(right - 100, (x1 + x2) / 2))
    attribute = (f' data-covid-measure="{html.escape(measure)}"'
                 if measure in COVID_CONTEXT["measure_contexts"] else "")
    return (f'<g class="covid-context"{attribute} pointer-events="none"><title>{html.escape(context["note"])}</title>'
            f'<rect class="covid-band" data-start-year="2020" data-end-year="2022" '
            f'x="{x1:.2f}" y="{top}" width="{x2 - x1:.2f}" height="{bottom - top}" '
            'fill="#D6D3CC" fill-opacity=".3" pointer-events="none"/>'
            f'<text class="covid-label" x="{centre:.2f}" y="{top - 10}" text-anchor="middle" '
            f'font-size="12" fill="#6B6B6B">{context["label"]}</text></g>')
