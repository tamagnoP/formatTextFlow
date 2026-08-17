# adjust_layers

An Inkscape extension that enforces one font family across a figure and sets font
sizes per layer, correcting for however much the containing group has been scaled.

## ASSUMPTIONS

**This extension is built around one specific figure convention. On a document that
doesn't follow it, the extension will change every piece of text to Arial and set no
sizes at all.** Read this section before installing.

**Layer names.** Font size is chosen from the layer a text element sits in — its
Inkscape label, not its XML id. The layer name is lowercased and matched against
these keywords:

| Layer name contains | Font size applied |
| ------------------- | ----------------- |
| `panel`             | 12 pt             |
| `label`             | 8 pt              |
| `ticks`             | 7 pt              |
| `scale`             | 6 pt              |
| `stats`             | 6 pt              |

Matching is by substring, so `Panel titles` and `tick labels` both match. Text in a
layer matching none of these keeps whatever size it already had.

If a layer name matches two keywords the extension picks one and records the
ambiguity in its report. Note that a layer called `Panel labels` matches both
`panel` and `label`, and resolves to **12 pt**, not 8 pt.

Only real Inkscape layers count. A plain group is transparent — text inside it takes
the size of the nearest enclosing layer. Sublayers do count, and a sublayer named
`ticks` inside a layer named `panel` gets 7 pt.

**Font.** `Arial`, hardcoded. It is applied to every `<text>` and `<flowRoot>` in the
document, including those in layers that match no size rule. There is no fallback
family, so on a system without Arial installed you get whatever your font
substitution does.

**Sizes and units.** Sizes are specified in points and written into the SVG as user
units. The conversion needs a document with a sensible `width`/`viewBox` pair; the
document's own display unit (mm, px, whatever) does not matter. Sizes are divided by
the composed transform at each text node, so a label in a group scaled to 40% still
renders at its target point size on the page.

**Element types.** `<text>` and `<tspan>`, plus Inkscape's flowed text
(`<flowRoot>`, `<flowPara>`, `<flowSpan>`). A `<tspan>` carrying a relative size
(`%`, `em`) or a `baseline-shift` is left alone, so superscripts and subscripts keep
their proportion.

**Everything else** in the document is untouched — no geometry, no colours, no new
elements. Only `font-size`, `font-family` and `-inkscape-font-specification`.

## Install

Copy both files into your user extensions folder:

    config/adjust_font-size_text/adjust_layers.py
    config/adjust_font-size_text/adjust_layers.inx

The exact folder is shown in Inkscape at **Edit ▸ Preferences ▸ System ▸ User
extensions**. By default it is:

| OS      | Path                                                                    |
| ------- | ----------------------------------------------------------------------- |
| Linux   | `~/.config/inkscape/extensions/`                                        |
| macOS   | `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/` |
| Windows | `%APPDATA%\inkscape\extensions\`                                        |

The two files must stay together, but they can sit in a subfolder of that directory
if you'd rather keep things tidy.

Restart Inkscape.

## Usage

**Extensions ▸ Text ▸ Adjust Font Levels by Layer**

There is nothing to select first, and no options to set — the extension processes
every text element in the document regardless of what is selected. Open a figure,
run it, done.

Each run writes a report to your home directory as
`adjust_layers_report<timestamp>.txt`, listing every text node with its layer, its
size before and after, the on-page size in points, and which rule matched. Layers
that matched more than one rule and groups with non-uniform scaling are called out
at the end. **This is one new file in your home directory per run**, so expect to
clear them out occasionally.

A summary line also appears in a dialog when the extension finishes.

To change the font, the sizes or the layer keywords, edit the constants at the top of
`AdjustFontLayers` in `adjust_layers.py`. Setting `DRY_RUN = True` near the top of
the file writes the report without modifying the document.

## Tested on

Inkscape 1.4.4 (macOS).

## License

MIT — see [LICENSE](LICENSE).
