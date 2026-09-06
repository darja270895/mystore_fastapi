import type { User, Product, Purchase } from "./types";

const API = "http://127.0.0.1:8000";

export async function getUsers(): Promise<User[]> {
    const response = await fetch(`${API}/users/`)

    if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
    }
    return response.json();
}

export async function createUser(
    name: string,
    email: string
): Promise<User> {
    const response = await fetch(`${API}/users/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            name,
            email,
        }),
    });

    if (!response.ok) {
        throw new Error("Failed to create user");
    }

    return response.json();
}
export async function getProducts(): Promise<Product[]> {
    const response = await fetch(`${API}/products/`);

    if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
    }

    return response.json();
}


export async function createProduct(
    name: string,
    price: number,
    stock: number
): Promise<Product> {
    const response = await fetch(`${API}/products/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            name,
            price,
            stock,
        }),
    });

    if (!response.ok) {
        throw new Error("Failed to create product");
    }

    return response.json();
}


export async function getPurchases(): Promise<Purchase[]> {
    const response = await fetch(`${API}/get_purchases/`);

    if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
    }

    return response.json();
}


export async function createPurchase(
    user_id: number,
    product_id: number,
    amount: number
): Promise<Purchase> {
    const response = await fetch(`${API}/buy`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            user_id,
            product_id,
            amount,
        }),
    });

    if (!response.ok) {
        throw new Error("Failed to create purchase");
    }

    return response.json();
}