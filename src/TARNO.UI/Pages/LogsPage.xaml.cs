using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using TARNO.UI.ViewModels;

namespace TARNO.UI.Pages;

public sealed partial class LogsPage : Page
{
    public MainViewModel? ViewModel { get; private set; }

    public LogsPage()
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
}
