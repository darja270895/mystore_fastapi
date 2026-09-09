import {mockPurchases} from "./purchases.mock";

// const API = "http://127.0.0.1:8000"


async function loadPurchases() {
    const responce: object = mockPurchases
    return responce
}

export default loadPurchases;