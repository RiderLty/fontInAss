

import qs from 'querystring';

const debug = (msg) => {
    ngx.log(ngx.ERR, msg);
}

const subtitlesHandler = async (r) => {
    const rawResponse = await ngx.fetch(`http://192.168.3.1:7096${r.uri}${qs.stringify(r.args) === "" ? "" : "?" + qs.stringify(r.args)}`)
    const rawBytes = await rawResponse.arrayBuffer();
    for (let key in rawResponse.headers) {
        r.headersOut[key] = rawResponse.headers[key]
    }
    try {
        const processedResponse = await ngx.fetch('http://192.168.3.128:8011/process_bytes', {
            method: 'POST',
            body: rawBytes
        });
        const processedBytes = await processedResponse.arrayBuffer();
        r.headersOut["Content-Length"] = processedBytes.length
        r.return(200, processedBytes);
    } catch (e) {
        r.headersOut["Subtitles-Handler-Error"] = String(e)
        r.return(200, rawBytes);
    }
}

export default { apiHandler, subtitlesHandler };


