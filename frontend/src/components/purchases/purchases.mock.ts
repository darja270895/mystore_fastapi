import type {Purchase} from "./purchases.types";

export const mockPurchases: Purchase[] = [
    {id: 1, user_id: 1, product_id: 1, amount: 100, date_value: Date.now()},
    {id: 2, user_id: 1, product_id: 2, amount: 50, date_value: Date.now()},
    {id: 3, user_id: 1, product_id: 3, amount: 2, date_value: Date.now()},
    {id: 4, user_id: 3, product_id: 1, amount: 100, date_value: Date.now()},
    {id: 5, user_id: 3, product_id: 3, amount: 10, date_value: Date.now()},
]

