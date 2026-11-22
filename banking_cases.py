"""Synthetic business rules and trusted candidate implementations."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from functools import partial


@dataclass(frozen=True)
class Candidate:
    id: str
    description: str
    implementation: Callable
    source: Callable | None = None


@dataclass(frozen=True)
class Check:
    description: str
    args: tuple
    expected: object


@dataclass(frozen=True)
class Rule:
    id: str
    requirement: str
    candidates: tuple[Candidate, ...]
    smoke: Check
    routine: tuple[Check, Check]
    focused: tuple[Check, Check]
    audit: tuple[Check, ...]


def fee(amount: str, rate: str, *, rounding=ROUND_HALF_UP) -> str:
    result = Decimal(amount) * Decimal(rate)
    return str(result.quantize(Decimal("0.01"), rounding=rounding))


def absolute_fee(amount: str, rate: str) -> str:
    return fee(str(abs(Decimal(amount))), rate)


def fee_with_integral_amount(amount: str, rate: str) -> str:
    return fee(str(int(Decimal(amount))), rate)


def booking_total(events, *, event_key=lambda account, event_id, amount: (account, event_id)):
    booked = {}
    for account, event_id, amount in events:
        booked.setdefault(event_key(account, event_id, amount), amount)
    return sum(booked.values())


def book_all(events):
    return sum(amount for _, _, amount in events)


def book_by_amount(events):
    return booking_total(events, event_key=lambda account, event_id, amount: (account, amount))


def book_by_event(events):
    return booking_total(events, event_key=lambda account, event_id, amount: event_id)


def affordable(income, essentials, obligations, instalment):
    return min(income, essentials, obligations, instalment) >= 0 and (
        income - essentials - obligations >= instalment
    )


def ignore_obligations(income, essentials, obligations, instalment):
    return affordable(income, essentials, 0, instalment)


def strict_surplus(income, essentials, obligations, instalment):
    return affordable(income, essentials, obligations, instalment + 1) and instalment >= 0


def accept_negative_costs(income, essentials, obligations, instalment):
    return income - essentials - obligations >= instalment


def statement(entries, start, end, *, include_end=False):
    return tuple(
        entry_id for day, entry_id in sorted(entries, key=lambda entry: entry[0])
        if start <= day < end or (include_end and start <= day == end)
    )


def statement_without_start(entries, start, end):
    return statement(entries, date.min, end)


def statement_sort_ties(entries, start, end):
    return statement(sorted(entries), start, end)


def refund(request, original, refunded):
    if request < 0:
        return 0
    return min(request, original - refunded)


def refund_ignores_previous(request, original, refunded):
    return refund(request, original, 0)


def refund_accepts_negative(request, original, refunded):
    return min(request, original - refunded)


def refund_fails_full_amount(request, original, refunded):
    remaining = original - refunded
    if request == remaining and request > 0:
        return request - 1
    return refund(request, original, refunded)


def settlement(trade_date, holidays, *, ignore_holidays=False, skip_once=False):
    day = trade_date + timedelta(days=1)
    while day.weekday() >= 5 or (day in holidays and not ignore_holidays):
        if skip_once and day.weekday() < 5:
            # This candidate handles one holiday but misses the next weekday closure.
            ignore_holidays = True
        day += timedelta(days=1)
    return day


def next_calendar_day(trade_date, holidays):
    return trade_date + timedelta(days=1)


D = date.fromisoformat

RULES = (
    Rule(
        "fee-rounding",
        "Multiply the signed amount by the rate and round half away from zero to cents.",
        (
            Candidate("reference", "Signed decimal arithmetic with half-up rounding", fee),
            Candidate("half-even", "Uses banker's rounding for half-cent ties", partial(fee, rounding=ROUND_HALF_EVEN)),
            Candidate("lost-sign", "Drops the sign of a reversal", absolute_fee),
            Candidate("truncated-amount", "Discards cents before calculating the fee", fee_with_integral_amount),
        ),
        Check("Whole amount", ("100", "0.02"), "2.00"),
        (
            Check("Small whole amount", ("8", "0.05"), "0.40"),
            Check("Large whole amount", ("2000", "0.01"), "20.00"),
        ),
        (
            Check("Positive half-cent tie", ("1", "0.005"), "0.01"),
            Check("Negative reversal", ("-100", "0.02"), "-2.00"),
        ),
        (
            Check("Negative half-cent tie", ("-5", "0.005"), "-0.03"),
            Check("Fee on fractional principal", ("9.80", "0.05"), "0.49"),
        ),
    ),
    Rule(
        "payment-retry",
        "Sum booked minor units once per (account, event ID). A retry keeps the first amount.",
        (
            Candidate("reference", "Deduplicates on account and event ID", booking_total),
            Candidate("no-deduplication", "Books duplicate delivery twice", book_all),
            Candidate("amount-key", "Treats distinct equal-amount events as duplicates", book_by_amount),
            Candidate("global-key", "Treats the event ID as globally unique", book_by_event),
        ),
        Check("Two distinct bookings", ((('a', 'p1', 100), ('a', 'p2', 200)),), 300),
        (
            Check("No events", ((),), 0),
            Check("Distinct event IDs across accounts", ((('a', 'p4', 900), ('b', 'p5', 115)),), 1015),
        ),
        (
            Check("Identical replay", ((('a', 'p9', 100), ('a', 'p9', 100)),), 100),
            Check("Different events with the same amount", ((('a', 'p9', 50), ('a', 'p10', 50)),), 100),
        ),
        (
            Check("Late replay with changed amount", ((('x', 'r1', 18), ('x', 'r1', 91)),), 18),
            Check("Shared event ID across accounts", ((('x', 'r2', 12), ('y', 'r2', 24)),), 36),
            Check("Equal credits under distinct IDs", ((('x', 'r3', 11), ('x', 'r4', 11)),), 22),
        ),
    ),
    Rule(
        "affordability",
        "Accept when all inputs in minor units are non-negative and disposable income covers the instalment, including equality.",
        (
            Candidate("reference", "Validates inputs and includes an exact match", affordable),
            Candidate("ignored-obligations", "Leaves out existing obligations", ignore_obligations),
            Candidate("strict-threshold", "Requires a positive surplus after payment", strict_surplus),
            Candidate("negative-costs", "Allows negative expenses to inflate disposable income", accept_negative_costs),
        ),
        Check("Income exceeds costs and instalment", (4000, 1500, 500, 900), True),
        (
            Check("Essentials consume most of the income", (2000, 1900, 0, 200), False),
            Check("Obligations make an instalment unaffordable", (3500, 1500, 1500, 800), False),
        ),
        (
            Check("Disposable amount exactly covers payment", (3000, 1900, 500, 600), True),
            Check("One minor unit below payment", (3000, 1900, 500, 601), False),
        ),
        (
            Check("No spare income after scheduled payment", (2500, 1400, 400, 700), True),
            Check("Invalid negative essential expense", (1500, -10, 400, 100), False),
            Check("Existing obligations push below threshold", (2510, 1300, 900, 500), False),
        ),
    ),
    Rule(
        "statement-window",
        "Include entries from the start date up to but excluding the end date. Preserve arrival order on same-day ties.",
        (
            Candidate("reference", "Uses a half-open range and stable date ordering", statement),
            Candidate("start-ignored", "Includes entries before the statement starts", statement_without_start),
            Candidate("end-inclusive", "Includes entries from the next statement period", partial(statement, include_end=True)),
            Candidate("tie-order", "Reorders same-day entries by identifier", statement_sort_ties),
        ),
        Check("One entry inside and one after range", (((D('2025-04-10'), 'a'), (D('2025-05-10'), 'b')), D('2025-04-01'), D('2025-05-01')), ('a',)),
        (
            Check("Empty statement", ((), D('2025-06-01'), D('2025-07-01')), ()),
            Check("Dates appear in chronological order", (((D('2025-06-13'), 'b'), (D('2025-06-02'), 'a')), D('2025-06-01'), D('2025-07-01')), ('a', 'b')),
        ),
        (
            Check("Start date is included and prior day excluded", (((D('2025-06-01'), 'a'), (D('2025-05-31'), 'b')), D('2025-06-01'), D('2025-07-01')), ('a',)),
            Check("End date is excluded", (((D('2025-06-30'), 'a'), (D('2025-07-01'), 'b')), D('2025-06-01'), D('2025-07-01')), ('a',)),
        ),
        (
            Check("Leap-day boundary", (((D('2024-02-28'), 'a'), (D('2024-02-29'), 'b'), (D('2024-03-01'), 'c')), D('2024-02-29'), D('2024-03-01')), ('b',)),
            Check("Same-day arrival order", (((D('2025-06-14'), 'z'), (D('2025-06-14'), 'a')), D('2025-06-13'), D('2025-06-15')), ('z', 'a')),
        ),
    ),
    Rule(
        "partial-refund",
        "Cap a refund at the unrefunded amount and treat a negative request as zero. Assume valid prior totals in minor units.",
        (
            Candidate("reference", "Respects remaining balance and zero floor", refund),
            Candidate("previous-ignored", "Computes the cap from the original payment", refund_ignores_previous),
            Candidate("negative-allowed", "Returns a negative refund", refund_accepts_negative),
            Candidate("one-cent-short", "Withholds a minor unit even when the full amount is refundable", refund_fails_full_amount),
        ),
        Check("Ordinary partial refund", (1000, 2400, 0), 1000),
        (
            Check("Full refund of untouched payment", (1700, 1700, 0), 1700),
            Check("Small refund after prior activity", (100, 5000, 170), 100),
        ),
        (
            Check("Request above unrefunded balance", (3000, 4000, 2000), 2000),
            Check("Negative request", (-1, 4000, 1000), 0),
        ),
        (
            Check("Second refund exactly uses balance", (321, 1000, 679), 321),
            Check("Additional refund after full refund", (7, 100, 100), 0),
            Check("Reversal sign in refund request", (-12, 100, 30), 0),
        ),
    ),
    Rule(
        "settlement-day",
        "Return the first weekday after the trade date that is absent from the supplied holiday calendar.",
        (
            Candidate("reference", "Skips weekends and all listed holidays", settlement),
            Candidate("no-weekend", "Only advances by one calendar day", next_calendar_day),
            Candidate("holiday-ignored", "Skips weekends but ignores holidays", partial(settlement, ignore_holidays=True)),
            Candidate("single-holiday", "Skips only the first listed holiday", partial(settlement, skip_once=True)),
        ),
        Check("Friday with no Monday holiday", (D('2025-01-10'), ()), D('2025-01-13')),
        (
            Check("Ordinary midweek settlement", (D('2025-01-14'), ()), D('2025-01-15')),
            Check("Holiday after the settlement day", (D('2025-01-15'), (D('2025-01-17'),)), D('2025-01-16')),
        ),
        (
            Check("Holiday immediately after trading", (D('2025-01-15'), (D('2025-01-16'),)), D('2025-01-17')),
            Check("Monday closure follows weekend", (D('2025-01-17'), (D('2025-01-20'),)), D('2025-01-21')),
        ),
        (
            Check("Consecutive weekday closures", (D('2025-12-23'), (D('2025-12-24'), D('2025-12-25'))), D('2025-12-26')),
            Check("First open weekday after Friday trade", (D('2025-02-07'), ()), D('2025-02-10')),
        ),
    ),
)
