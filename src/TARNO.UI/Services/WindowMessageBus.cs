using System;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;

namespace TARNO.UI.Services;

/// <summary>
/// In-Process-Nachrichtenbus für fensterübergreifende UI-Events.
/// Ersatz für BroadcastChannel/SharedWorker in einer reinen WinUI 3 App.
/// Alle Nachrichten werden auf dem DispatcherQueue des Ziel-Fensters
/// zugestellt, damit UI-Updates thread-sicher erfolgen.
/// </summary>
public static class WindowMessageBus
{
    public static void Publish<TMessage>(TMessage message)
        where TMessage : class
    {
        WeakReferenceMessenger.Default.Send(message);
    }

    public static void Subscribe<TMessage>(object recipient, Action<TMessage> handler)
        where TMessage : class
    {
        WeakReferenceMessenger.Default.Register<TMessage>(recipient, (r, m) =>
        {
            if (recipient is FrameworkElement fe && fe.DispatcherQueue is not null)
            {
                _ = fe.DispatcherQueue.TryEnqueue(DispatcherQueuePriority.Normal, () => handler(m));
            }
            else
            {
                handler(m);
            }
        });
    }

    public static void Unsubscribe<TMessage>(object recipient)
        where TMessage : class
    {
        WeakReferenceMessenger.Default.Unregister<TMessage>(recipient);
    }

    public static void UnsubscribeAll(object recipient)
    {
        WeakReferenceMessenger.Default.UnregisterAll(recipient);
    }
}

public record ProviderChangedMessage(string Provider, string Model);

public record ChatMessageReceivedMessage(string ChatId, string Role, string Text);

public record PanelStateChangedMessage(string PanelId, string State, int WindowIndex);
