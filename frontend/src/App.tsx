import './App.css'
import AppMain from './components/app-main/AppMain'
import {AppLayout} from "./components/ui/AppLayout";

// const API = "http://127.0.0.1:8000"

// JS function that returns markup.
function App() {
    return (
        <div>
            <AppLayout>
                <AppMain/>
            </AppLayout>
        </div>
    );
}

export default App;
