# Examples

The same task answered two ways: with no skill (`## Without adderall`) and with
adderall (`## With Adderall`), so you can compare side by side.

The `With adderall` outputs are adapted from the published ponytail benchmark
runs (Claude Haiku 4.5), with the `ponytail:` shortcut marker renamed to
`adderall:`. Adderall adds the output-shaping layer on top: the code is the
laziest thing that works, and the prose around it leads with the next action
and ends there.

| Example | Without (LOC) | With (LOC) |
|---|--:|--:|
| [Email Validation](email-validation.md) | 75 | 3 |
| [Debounce](debounce.md) | 116 | 10 |
| [CSV Sum](csv-sum.md) | 20 | 3 |
| [Countdown Timer](react-countdown.md) | 267 | 9 |
| [Rate Limiting](rate-limit.md) | 128 | 10 |
| [Deep Clone](deep-clone.md) | dep | built-in |
| [URL Parameters](url-params.md) | dep | built-in |
| [Group By](group-by.md) | dep | built-in |
| [Number Formatting](number-formatting.md) | dep | built-in |
| [Infinite Scroll](infinite-scroll.md) | dep | built-in |
| [Modal Dialog](modal-dialog.md) | dep | built-in |

The pattern in every one: an over-build trap (a dependency, a wrapper class, a
config object) replaced by the stdlib or native-platform rung of the ladder,
and a feature tour replaced by one skipped-line and one next action.
