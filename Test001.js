addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  // Get the URL parameter from the query string
  const url = new URL(request.url)
  const link = url.searchParams.get('url')
  
  if (!link) {
    return new Response('Please provide a URL parameter, e.g., ?url=[your_link]', { 
      status: 400,
      headers: { 'Content-Type': 'text/plain' }
    })
  }

  try {
    // Step 1: Fetch data from the original API
    const apiUrl = `https://teradl1.vercel.app/api?url=${encodeURIComponent(link)}`
    const apiResponse = await fetch(apiUrl)
    const apiData = await apiResponse.json()

    // Check if API response is successful and contains download link
    if (apiData.status !== 'success' || !apiData['Extracted Info']?.[0]?.['Direct Download Link']) {
      return new Response(JSON.stringify(apiData), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    // Step 2: Get the direct download link
    const downloadLink = apiData['Extracted Info'][0]['Direct Download Link']
    const fileName = apiData['Extracted Info'][0]['Title'] || 'download'

    // Step 3: Fetch the file from the download link
    const fileResponse = await fetch(downloadLink)

    // Check if the file fetch was successful
    if (!fileResponse.ok) {
      return new Response(`Failed to fetch file from ${downloadLink}`, {
        status: fileResponse.status,
        headers: { 'Content-Type': 'text/plain' }
      })
    }

    // Step 4: Create a response that will trigger a download
    const responseHeaders = new Headers(fileResponse.headers)
    responseHeaders.set('Content-Disposition', `attachment; filename="${fileName}"`)
    
    return new Response(fileResponse.body, {
      headers: responseHeaders,
      status: fileResponse.status
    })

  } catch (error) {
    return new Response(`Error: ${error.message}`, {
      status: 500,
      headers: { 'Content-Type': 'text/plain' }
    })
  }
}
