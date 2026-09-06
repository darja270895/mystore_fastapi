import loadProducts from "./load-products";
import {useEffect, useState} from "react";
import '../../App.css'


interface Product {
    id: number;
    name: string;
    stock: string;
    price: number;
}


const ProductsInfo = () => {
    const [products, setProducts] = useState<Product[]>([]);

    async function handleLoadProducts() {
        const users = await loadProducts();
        console.log(users);
        setProducts(users);
    }

    useEffect(() => {
        handleLoadProducts();
    }, []);

    return (
        <section className="dashboard-section">
            <button className="button" onClick={handleLoadProducts}>
                Refresh
            </button>
            <table>
                <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Stock</th>
                    <th>Price</th>
                </tr>
                </thead>
                <tbody>
                {products.map((product) => (
                    <tr key={product.id}>
                        <td>{product.id}</td>
                        <td>{product.name}</td>
                        <td>{product.stock}</td>
                        <td>{product.price}</td>
                    </tr>
                ))}
                </tbody>
            </table>
        </section>
    )
}

export default ProductsInfo;