
const API = "http://127.0.0.1:8000"

async function loadProducts(){
    const response = await fetch(`${API}/products/`)
    if (!response.ok){
        throw new Error(`HTTP error: ${response.status}`);
    }
    return response.json()
}

export default loadProducts;