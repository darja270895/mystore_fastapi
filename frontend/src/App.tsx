import {useEffect} from "react";
import './App.css'
import AppMain from './components/app-main/AppMain'

const API = "http://127.0.0.1:8000"

// Component. That's a JS function that returns markup.
function App() {

    // JSX syntaxis
    // Wrap with <div></div> or <> </>

    async function loadPurchases() {
        const response = await fetch(`${API}/get_purchases/`);
        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }
        const purchases = await response.json();
        const table = document.getElementById("purchasesTable");
        if (!table) return;
        table.innerHTML = "";
        purchases.forEach((purchase: any) => {
            const row = document.createElement("tr");
            row.innerHTML = ` 
             <td>${purchase.id}</td> 
             <td>${purchase.user_id}</td> 
             <td>${purchase.product_id}</td> 
             <td>${purchase.amount}</td> 
             <td> ${purchase.created_at ? new Date(purchase.created_at).toLocaleString() : "—"} </td> `;
            table.appendChild(row);
        });
    }

    useEffect(() => {
        // loadUsers();
        // loadProducts();
        loadPurchases();
    }, []);
    return (
        <div>
            <AppMain/>



         </div>
    );
}

export default App;
