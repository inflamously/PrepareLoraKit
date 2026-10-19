# Browser UI conventions

## Scrolling and overflow (CSS)

A box that scrolls on one axis must state the other axis too. Omitting it is not
"no scrolling": when one axis is not `visible`, the other computes from `visible`
to `auto`, so a lone `overflow-y: auto` silently makes the box a horizontal
scroll container as well. Clamp the idle axis with the pair

```css
overflow-x: hidden;
overflow-x: clip;   /* engines below Chromium 90 / WebKitGTK 2.38 drop this */
```

`clip` rather than `hidden` because `hidden` still leaves a scroll container:
it only removes the scrollbar while the browser goes on scrolling the box on
focus and on `scrollIntoView`, stranding a pane offset with no way to scroll it
back. Make content fit *before* clamping an axis — clamping first only trades a
visible scrollbar for invisible clipping. `tests/ui/static/css_overflow.test.js`
enforces both halves of this and rejects the `overflow: auto` shorthand, so
intent is always written out. The rationale lives in
`prepare_lora_kit_ui/static/core/foundation.css`.
