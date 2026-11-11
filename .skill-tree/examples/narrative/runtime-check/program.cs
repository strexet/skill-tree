#nullable enable
using System.Text.Json;
using Ink.Runtime;

var compiled = File.ReadAllText(args[0]);
using var source = JsonDocument.Parse(File.ReadAllText(args[1]));
var cases = source.RootElement.GetProperty("cases").EnumerateArray();
var pilot = cases.Single(item => item.GetProperty("id").GetString() == "ridge-pilot");
var traces = pilot.GetProperty("traces").EnumerateArray().ToArray();
if (traces.Length == 0)
    throw new InvalidOperationException("The declared Ink pilot has no traces");

var negative = Environment.GetEnvironmentVariable("NARRATIVE_INK_NEGATIVE_CONTROL") == "duplicate-choice";
if (negative)
    compiled = compiled.Replace("choice-id: skip-log", "choice-id: discover-log", StringComparison.Ordinal);

try
{
    foreach (var trace in traces)
        Replay(compiled, trace);
}
catch (InvalidOperationException error)
{
    Console.Error.WriteLine(error.Message);
    return 1;
}

var tagged = new Story(compiled);
tagged.ContinueMaximally();
Equal("Read the relay log by the selector.", ChoiceMap(tagged)["discover-log"].text.Trim());
var renamed = new Story(compiled.Replace("Read the relay log by the selector.", "Inspect the relay log.", StringComparison.Ordinal));
renamed.ContinueMaximally();
Equal("Inspect the relay log.", ChoiceMap(renamed)["discover-log"].text.Trim());
Equal("discover-log,skip-log", string.Join(",", ChoiceMap(renamed).Keys.Order()));
Console.WriteLine("PASS renamed label preserves identity");

var duplicate = new Story(compiled.Replace("choice-id: skip-log", "choice-id: discover-log", StringComparison.Ordinal));
duplicate.ContinueMaximally();
try
{
    ChoiceMap(duplicate);
    throw new InvalidOperationException("Expected duplicate active identity");
}
catch (InvalidOperationException error) when (error.Message == "Duplicate active choice ID discover-log")
{
}
Console.WriteLine("PASS duplicate active identity is diagnosed");
return 0;

static void Replay(string compiled, JsonElement trace)
{
    var id = trace.GetProperty("id").GetString();
    var story = new Story(compiled);
    AssertState(story, trace.GetProperty("initial_state"));
    var output = story.ContinueMaximally();
    Contains(output, "A blue seal");
    foreach (var step in trace.GetProperty("steps").EnumerateArray())
    {
        var beat = step.GetProperty("node").GetString();
        var action = step.TryGetProperty("action", out var actionValue) ? actionValue.GetString() : null;
        try
        {
            var choices = ChoiceMap(story);
            var expected = step.GetProperty("offered").EnumerateArray().Select(value => value.GetString()).Order();
            Equal(string.Join(",", expected), string.Join(",", choices.Keys.Order()));
            if (step.TryGetProperty("feedback", out var feedback))
                foreach (var marker in feedback.EnumerateArray())
                    Contains(output, marker.GetString()!);
            if (step.TryGetProperty("exposure", out var exposure))
            {
                var logExposed = exposure.EnumerateArray().Any(item => item.GetString() == "scene-relay");
                Equal(logExposed, output.Contains("06:12. Heater cable insulation failed", StringComparison.Ordinal));
                if (logExposed)
                {
                    Contains(output, "06:24. Maintenance fitted the last spare fuse");
                    Contains(output, "06:40. First lightning");
                }
                else
                {
                    Equal(false, output.Contains("The pack is good", StringComparison.Ordinal));
                }
            }
            if (step.TryGetProperty("save_point", out var save) && save.GetBoolean())
            {
                var restored = new Story(compiled);
                restored.state.LoadJson(story.state.ToJson());
                var restoredChoices = ChoiceMap(restored);
                Equal(string.Join(",", choices.Keys.Order()), string.Join(",", restoredChoices.Keys.Order()));
                foreach (var choice in choices)
                    Equal(choice.Value.text, restoredChoices[choice.Key].text);
                story = restored;
                choices = restoredChoices;
            }
            if (action == null)
            {
                Equal("terminal", trace.GetProperty("expected_exit").GetString());
                Equal(false, story.canContinue);
                Equal(0, choices.Count);
                AssertState(story, trace.GetProperty("expected_state"));
            }
            else
            {
                if (!choices.TryGetValue(action, out var choice))
                    throw new InvalidOperationException($"Unavailable declared action '{action}'");
                story.ChooseChoiceIndex(choice.index);
                output = story.ContinueMaximally();
            }
        }
        catch (InvalidOperationException error)
        {
            throw new InvalidOperationException($"Trace '{id}', beat '{beat}', action '{action}': {error.Message}", error);
        }
    }
    Console.WriteLine($"PASS {id}");
}

static void AssertState(Story story, JsonElement state)
{
    foreach (var item in state.EnumerateObject())
    {
        var actual = JsonSerializer.Serialize(story.variablesState[item.Name]);
        if (item.Value.GetRawText() != actual)
            throw new InvalidOperationException($"State '{item.Name}' expected {item.Value.GetRawText()}, received {actual}");
    }
}

static void Contains(string actual, string expected)
{
    if (!actual.Contains(expected, StringComparison.Ordinal))
        throw new InvalidOperationException($"Expected visible cue '{expected}'");
}

static void Equal(object? expected, object? actual)
{
    if (!Equals(expected, actual))
        throw new InvalidOperationException($"Expected '{expected}', received '{actual}'");
}

static Dictionary<string, Choice> ChoiceMap(Story story)
{
    const string prefix = "choice-id:";
    var result = new Dictionary<string, Choice>(StringComparer.Ordinal);
    foreach (var choice in story.currentChoices)
    {
        var tags = (choice.tags ?? new List<string>())
            .Where(tag => tag.StartsWith(prefix, StringComparison.Ordinal)).ToArray();
        if (tags.Length != 1)
            throw new InvalidOperationException($"Expected one identity for active choice '{choice.text}'");
        var id = tags[0][prefix.Length..].Trim();
        if (id.Length == 0)
            throw new InvalidOperationException($"Missing identity for active choice '{choice.text}'");
        if (!result.TryAdd(id, choice))
            throw new InvalidOperationException($"Duplicate active choice ID {id}");
    }
    return result;
}
