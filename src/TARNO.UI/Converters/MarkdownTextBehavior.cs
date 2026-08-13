using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Documents;
using Microsoft.UI.Xaml.Media;

namespace TARNO.UI.Converters;

/// <summary>
/// Attached property that renders a lightweight Markdown subset (bold,
/// italic, ### headings, --- rules, - list items) into a RichTextBlock's
/// Blocks. LLM responses often contain raw Markdown syntax that must not
/// be shown verbatim to the user (see Lead-UX-Briefing 2026-07-14) — this
/// avoids pulling in an experimental/heavyweight Markdown-rendering
/// package for a WinUI 3 app whose WindowsAppSDK version compatibility
/// isn't guaranteed, at the cost of only covering the common subset LLMs
/// actually produce.
/// </summary>
public static class MarkdownTextBehavior
{
    public static readonly DependencyProperty MarkdownProperty = DependencyProperty.RegisterAttached(
        "Markdown",
        typeof(string),
        typeof(MarkdownTextBehavior),
        new PropertyMetadata(null, OnMarkdownChanged));

    public static string GetMarkdown(RichTextBlock element) => (string)element.GetValue(MarkdownProperty);

    public static void SetMarkdown(RichTextBlock element, string value) => element.SetValue(MarkdownProperty, value);

    private static readonly Regex InlineTokenPattern = new(
        @"\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*|_(.+?)_",
        RegexOptions.Compiled);

    private static void OnMarkdownChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not RichTextBlock richTextBlock)
        {
            return;
        }

        richTextBlock.Blocks.Clear();
        var text = e.NewValue as string ?? string.Empty;
        if (string.IsNullOrEmpty(text))
        {
            richTextBlock.Blocks.Add(new Paragraph());
            return;
        }

        // WinUI TextBox represents soft line breaks (Shift+Enter) as a bare
        // '\r', not '\n' or '\r\n' - split on all three so heading/rule/list
        // detection actually runs per visual line instead of treating a
        // multi-line message as one blob.
        foreach (var line in text.Split(new[] { "\r\n", "\r", "\n" }, StringSplitOptions.None))
        {
            richTextBlock.Blocks.Add(RenderLine(line));
        }
    }

    private static Paragraph RenderLine(string line)
    {
        var trimmed = line.TrimStart();

        if (trimmed is "---" or "***" or "___")
        {
            var rule = new Paragraph { Margin = new Thickness(0, 6, 0, 6) };
            var ruleBorder = new Microsoft.UI.Xaml.Shapes.Rectangle
            {
                Height = 1,
                Width = 400,
                Fill = new SolidColorBrush(Windows.UI.Color.FromArgb(40, 255, 255, 255)),
            };
            rule.Inlines.Add(new InlineUIContainer { Child = ruleBorder });
            return rule;
        }

        if (trimmed.StartsWith("### "))
        {
            var paragraph = new Paragraph { FontSize = 16, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Margin = new Thickness(0, 4, 0, 2) };
            AddInlines(paragraph.Inlines, trimmed[4..]);
            return paragraph;
        }

        if (trimmed.StartsWith("## "))
        {
            var paragraph = new Paragraph { FontSize = 17, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Margin = new Thickness(0, 4, 0, 2) };
            AddInlines(paragraph.Inlines, trimmed[3..]);
            return paragraph;
        }

        if (trimmed.StartsWith("- ") || trimmed.StartsWith("* "))
        {
            var paragraph = new Paragraph();
            paragraph.Inlines.Add(new Run { Text = "•  " });
            AddInlines(paragraph.Inlines, trimmed[2..]);
            return paragraph;
        }

        var plain = new Paragraph();
        AddInlines(plain.Inlines, line);
        return plain;
    }

    private static void AddInlines(InlineCollection inlines, string text)
    {
        var lastIndex = 0;
        foreach (Match match in InlineTokenPattern.Matches(text))
        {
            if (match.Index > lastIndex)
            {
                inlines.Add(new Run { Text = text[lastIndex..match.Index] });
            }

            if (match.Groups[1].Success || match.Groups[2].Success)
            {
                var boldText = match.Groups[1].Success ? match.Groups[1].Value : match.Groups[2].Value;
                inlines.Add(new Bold { Inlines = { new Run { Text = boldText } } });
            }
            else
            {
                var italicText = match.Groups[3].Success ? match.Groups[3].Value : match.Groups[4].Value;
                inlines.Add(new Italic { Inlines = { new Run { Text = italicText } } });
            }

            lastIndex = match.Index + match.Length;
        }

        if (lastIndex < text.Length)
        {
            inlines.Add(new Run { Text = text[lastIndex..] });
        }
    }
}
