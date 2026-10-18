ObjC.import("Vision");
ObjC.import("Foundation");

function run(argv) {
  var data = $.NSData.dataWithContentsOfFile(argv[0]);
  if (!data || data.isNil() || Number(data.length) === 0) return "ERR not an image";
  var request = $.VNClassifyImageRequest.alloc.init;
  var handler = $.VNImageRequestHandler.alloc["initWithData:options:"](data, undefined);
  var error = Ref();
  var requests = $.NSMutableArray.alloc.init;
  requests.addObject(request);
  if (!handler.performRequestsError(requests, error)) {
    return "ERR " + (error[0] ? error[0].localizedDescription.js : "classifier failed");
  }
  var results = request.results;
  var lines = [];
  var count = results ? Number(results.count) : 0;
  for (var i = 0; i < count; i++) {
    var obs = results.objectAtIndex(i);
    if (Number(obs.confidence) >= 0.05) lines.push(ObjC.unwrap(obs.identifier) + "\t" + obs.confidence);
  }
  return lines.join("\n");
}
