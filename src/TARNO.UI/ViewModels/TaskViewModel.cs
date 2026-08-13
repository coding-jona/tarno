using CommunityToolkit.Mvvm.ComponentModel;
using System;

namespace TARNO.UI.ViewModels;

/// <summary>
/// Represents a task pushed by the backend via gRPC TaskUpdate messages.
/// Keeps the UI task list in sync with the Python pipeline.
/// </summary>
public partial class TaskViewModel : ObservableObject
{
    [ObservableProperty]
    private string _id = string.Empty;

    [ObservableProperty]
    private string _title = string.Empty;

    [ObservableProperty]
    private string _status = "pending";

    [ObservableProperty]
    private int _progress;

    [ObservableProperty]
    private DateTimeOffset _createdAt = DateTimeOffset.Now;
}
