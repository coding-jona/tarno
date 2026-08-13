using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;

namespace TARNO.UI.Pages;

public sealed partial class HomePage : Page
{
    public MainViewModel? ViewModel { get; private set; }

    public HomePage()
    {
        this.InitializeComponent();
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
        }
        base.OnNavigatedTo(e);
    }

    private void OpenVoice(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("HomePage", "OpenVoice");
        ViewModel?.SelectPage(AppPage.Voice);
    }

    private void OpenChat(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("HomePage", "OpenChat");
        ViewModel?.SelectPage(AppPage.Chat);
    }
}
