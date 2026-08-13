using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Liest und schreibt Chat-Sitzungen nach %LOCALAPPDATA%\TARNO\chats.json.
/// </summary>
public static class ChatStore
{
    private const string ChatsFileName = "chats.json";

    public static string GetChatsPath()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string tarnoDir = Path.Combine(localAppData, "TARNO");
        if (!Directory.Exists(tarnoDir))
        {
            Directory.CreateDirectory(tarnoDir);
        }
        return Path.Combine(tarnoDir, ChatsFileName);
    }

    public static List<ChatSession> Load()
    {
        try
        {
            string path = GetChatsPath();
            if (File.Exists(path))
            {
                string json = File.ReadAllText(path);
                var sessions = JsonSerializer.Deserialize<List<ChatSession>>(json);
                if (sessions is not null)
                {
                    foreach (var session in sessions)
                    {
                        session.Messages ??= new List<ChatMessageData>();
                    }
                    return sessions.OrderByDescending(s => s.UpdatedAt).ToList();
                }
            }
        }
        catch
        {
            // Best-effort: bei Korruption leere Liste zurückgeben.
        }
        return new List<ChatSession>();
    }

    public static void Save(List<ChatSession> sessions)
    {
        try
        {
            string path = GetChatsPath();
            string json = JsonSerializer.Serialize(sessions, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(path, json);
        }
        catch
        {
            // Speichern ist best-effort.
        }
    }

    public static void SaveSession(ChatSession session)
    {
        var sessions = Load();
        int index = sessions.FindIndex(s => s.Id == session.Id);
        session.UpdatedAt = DateTimeOffset.Now;
        if (index >= 0)
        {
            sessions[index] = session;
        }
        else
        {
            sessions.Insert(0, session);
        }
        Save(sessions);
    }

    public static void Delete(string id)
    {
        var sessions = Load();
        sessions.RemoveAll(s => s.Id == id);
        Save(sessions);
    }
}
