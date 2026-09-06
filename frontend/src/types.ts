export interface User {
    id: number;
    name: string;
    email: string;
}

export interface Product {
    id: number;
    name: string;
    stock: number;
    price: number;
}

export interface Purchase {
    id: number;
    user_id: number;
    product_id: number;
    amount: number;
    created_at?: string;
}