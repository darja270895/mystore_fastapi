export interface Purchase {
    id: number;
    user_id: number;
    product_id: number;
    amount: number;
    date_value: number,
    image_path?: string,
    increase: boolean
}