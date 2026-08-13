using Microsoft.UI.Xaml.Data;
using System;

namespace TARNO.UI.Converters;

/// <summary>Phase D: Anzeigename für den aktiven LLM-Provider.</summary>
public sealed class ProviderToLabelConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        return (value as string) switch
        {
            "mistral" => "Mistral",
            "claude" => "Claude",
            "gemini" => "Gemini",
            "groq" => "Groq",
            "huggingface" => "Hugging Face",
            "ollama" => "Ollama",
            _ => value as string ?? "Unbekannt",
        };
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotSupportedException();
    }
}
