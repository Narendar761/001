addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  // Parse the URL to extract query parameters
  const url = new URL(request.url);
  const phoneNumber = url.searchParams.get('number');
  const name = url.searchParams.get('message');

  // Validate query parameters
  if (!phoneNumber || !name) {
    return new Response(JSON.stringify({
      error: 'Missing required parameters: number and message'
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // API endpoint and headers
  const apiUrl = 'https://appbowl.com/api/sms/send-sms';
  const headers = {
    'Host': 'appbowl.com',
    'Connection': 'keep-alive',
    'sec-ch-ua-platform': '"Android"',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    'DNT': '1',
    'Content-Type': 'application/json',
    'sec-ch-ua-mobile': '?1',
    'Accept': '*/*',
    'Origin': 'https://www.appbowl.com',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'Referer': 'https://www.appbowl.com/',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8,bn;q=0.7'
  };

  // Prepare the POST request body
  const body = JSON.stringify({
    name: name,
    mobile: phoneNumber
  });

  try {
    // Make the POST request to the external API
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: headers,
      body: body
    });

    // Get the response body
    const responseText = await response.text();

    // Return the API response to the client
    return new Response(responseText, {
      status: response.status,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    // Handle errors
    return new Response(JSON.stringify({
      error: 'Failed to process request',
      details: error.message
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}