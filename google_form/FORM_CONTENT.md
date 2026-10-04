# Google Form contents

The form is created automatically by `create_forms.gs` (see the steps at the top of that file). This page lists the questions for reading and review. The code at the start of each question (A1, B3, …) is how the analysis script finds it, so keep the codes if you change any wording.

## Customer survey (share with friends, family, WhatsApp groups)

| Code | Question | Answer type | Feeds |
|---|---|---|---|
| A1 | Your age | single choice | weighting |
| A2 | Where do you live? (metro / large city / small town / village) | single choice | weighting |
| A3 | How often do you order online? *"Rarely or never" ends the form* | single choice | screening |
| A4 | Have you ordered from Meesho? | single choice | segment |
| A5 | How do you usually pay? (almost always COD / mix / almost always online) | single choice | **main segment: COD users** |
| A6 | What do you buy online most often? (up to 3) | checkboxes | context |
| B1 | In the last 12 months, has a parcel gone back undelivered? *"No" skips to C* | single choice | share with a failed delivery |
| B2 | How many times? | single choice | frequency |
| B3 | Most recent time, main reason? (10 options + Other) | single choice | **reason mix (P1, P3)** |
| B4 | How had you paid for that order? | single choice | COD check |
| B5 | Days until it arrived? | single choice | lateness as a cause |
| B6 | What would have helped you accept it? | checkboxes | which fixes matter |
| C1 | No cash: would you pay by UPI at the door? | 4-point scale | **fix rate: no cash** |
| C2 | Not home today: pick a new date on WhatsApp? | 4-point scale | **fix rate: reschedule** |
| C3 | Not home: leave with neighbour/kirana within 1 km? | 4-point scale | **fix rate: not home** |
| C4 | Rider can't find you: send exact location on WhatsApp? | 4-point scale | **fix rate: address** |
| C5 | Wrong size: accept a free exchange? | 4-point scale | **fix rate: exchange** |
| D1 | Would you accept a sealed parcel someone else refused? | single choice | **buyer acceptance (P2, P3)** |
| D2 | More okay if it arrives 2–3 days faster? | single choice | how to pitch it |
| D3 | Want to be told? | single choice | product design |
| D4 | What would worry you? | checkboxes | condition-check rules |
| E1 | How do you find clothes online? | single choice | demand concentration (directional) |
| E2 | Ever ordered exactly the same product as someone you know? | single choice | demand concentration (directional) |
| E3 | First 3 digits of your PIN (optional) | text, validated | **district grouping (Kanpur = 208)** |
| E4 | Anything else? | paragraph | quotes |

The 4-point scale is: Definitely yes / Probably yes / Probably not / Definitely not.

## Export

In the form, go to Responses → the green Sheets icon → open the sheet → File → Download → CSV. Save the file as:

- `data/raw/survey_responses.csv`
