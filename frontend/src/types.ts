export interface User {
    id: number;
    name: string;
    email: string;
}

export interface UserCreate {
    name: string;
    email: string;
}

export interface Product {
    id: number;
    name: string;
    stock: number;
    price: number;
}

export interface ProductCreate {
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

export interface PurchaseCreate {
    user_id: number;
    product_id: number;
    amount: number;
}

export interface CardItem {
    product_id: number;
    product_name: string | null;
    amount: number;
}

export interface Card {
    user_id: number;
    items: CardItem[];
    total_items: number;
}

export interface CardAdd {
    user_id: number;
    product_id: number;
    amount: number;
}

export interface CardRemove {
    user_id: number;
    product_id: number;
}

export interface CardPublishResponse {
    status: string;
    event_id: string;
    channel: string;
    card: Card;
}

export interface RecentPurchase {
    purchase_id: number;
    user_id: number;
    product_id: number;
    amount: number;
    product_name: string;
    total_price: number;
    created_at?: string;
}

export interface StockMovement {
    id: number;
    product_id: number;
    delta: number;
    reason: string;
    purchase_id: number | null;
    created_at?: string;
}

export interface Notification {
    id: number;
    user_id: number;
    kind: string;
    payload: string;
    is_read: boolean;
    created_at?: string;
}
