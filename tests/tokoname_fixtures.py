"""公開ページの構造を模した自作HTML。実際の氏名・オッズは転載しない。"""

import json
from itertools import permutations


def html(page="odds", deadline="12:00", day="20261104", race=1):
    kind = "Odds1" if page == "odds" else "0"
    head = '<div class="sub-tabs"><li class="selected"><a '
    head += f'data-day="{day}" data-race="{race}" data-kind="{kind}"></a></li></div>'
    clock = f'<dd class="raceinfo_dento_time">{deadline}</dd>'
    head += (
        '<script>$(".race_number", parent.document).html('
        + json.dumps(f"{race}R")
        + ');$(".race_deadline", parent.document).html('
        + json.dumps(clock)
        + ");</script>"
    )
    if page == "odds":
        for first in range(1, 7):
            head += f'<table class="odds3Tan"><tr><td class="chaku_left1">{first}</td></tr>'
            for second in range(1, 7):
                if second == first:
                    continue
                for index, third in enumerate(n for n in range(1, 7) if n not in (first, second)):
                    head += "<tr>"
                    if index == 0:
                        head += f'<td class="chaku_2" rowspan="4">{second}</td>'
                    head += (
                        f'<td class="chaku_3">{third}</td><td class="odds">'
                        f"{first * 100 + second * 10 + third / 10:.1f}</td></tr>"
                    )
            head += "</table>"
    else:
        head += "<table>"
        for boat in range(1, 7):
            head += f'<tr><td class="waku">{boat}</td><td><li class="com-toban">B1/900{boat}</li>'
            head += f'<li class="com-rname">架空選手{boat}</li></td>'
            if page == "entries":
                for col, upper, lower in [
                    (6, "5.47", "36.6"),
                    (8, "33", "36.8"),
                    (9, "69", "30.4"),
                ]:
                    head += f'<td class="col{col}"><span class="ue">{upper}</span>'
                    head += f'<span class="shita">{lower}</span></td>'
            else:
                for col, value in [(3, "-.--"), (4, "52.0"), (5, "-0.5"), (10, "")]:
                    head += f'<td class="col{col}">{value}</td>'
            head += "</tr>"
        head += "</table>"
    return head.encode()


def combinations():
    return {"-".join(map(str, p)) for p in permutations(range(1, 7), 3)}
