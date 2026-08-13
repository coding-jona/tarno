using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using TARNO.UI.Pages;
using TARNO.UI.ViewModels;

namespace TARNO.UI.UserControls;

public sealed partial class ChatView : UserControl
{
    private MainViewModel? _pendingViewModel;

    public ChatView()
    {
        this.InitializeComponent();
        DataContextChanged += OnDataContextChanged;
        Loaded += OnLoaded;
    }

    private void OnDataContextChanged(FrameworkElement sender, DataContextChangedEventArgs e)
    {
        if (e.NewValue is MainViewModel vm)
        {
            _pendingViewModel = vm;
            NavigateIfReady();
        }
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        NavigateIfReady();
    }

    private void NavigateIfReady()
    {
        if (_pendingViewModel is null || ChatFrame is null)
        {
            return;
        }

        ChatFrame.Navigate(typeof(ChatPage), _pendingViewModel);
        _pendingViewModel = null;
    }
}
