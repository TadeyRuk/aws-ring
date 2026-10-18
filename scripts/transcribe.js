ObjC.import("Speech");
ObjC.import("Foundation");

function run(argv) {
  var url = $.NSURL.fileURLWithPath(argv[0]);
  var recognizer = $.SFSpeechRecognizer.alloc.initWithLocale($.NSLocale.alloc.initWithLocaleIdentifier("en-US"));
  if (!recognizer || recognizer.isNil() || !recognizer.isAvailable) return "ERR recognizer unavailable";
  var request = $.SFSpeechURLRecognitionRequest.alloc.initWithURL(url);
  request.shouldReportPartialResults = false;
  var status = Number($.SFSpeechRecognizer.authorizationStatus);
  if (status !== 3) {
    var authDone = false;
    $.SFSpeechRecognizer.requestAuthorization(function (next) {
      status = Number(next);
      authDone = true;
    });
    var authUntil = Date.now() + 8000;
    while (!authDone && Date.now() < authUntil) {
      $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.2));
    }
  }
  if (Number(status) !== 3) return "ERR speech authorization " + status;
  var done = false;
  var text = "";
  var failed = "";
  recognizer.recognitionTaskWithRequestResultHandler(request, function (result, error) {
    if (result && !result.isNil() && result.isFinal) {
      text = ObjC.unwrap(result.bestTranscription.formattedString);
      done = true;
    } else if (error && (!result || result.isNil())) {
      failed = String(error);
      done = true;
    }
  });
  var until = Date.now() + 20000;
  while (!done && Date.now() < until) {
    $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.2));
  }
  if (failed) return "ERR " + failed;
  if (!done) return "ERR transcription timed out";
  return text;
}
