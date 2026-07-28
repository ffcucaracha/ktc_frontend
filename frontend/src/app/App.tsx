import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";

import { AppProviders } from "./providers";
import { AppRouter } from "./routes";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1b5e20",
    },
    secondary: {
      main: "#005b96",
    },
    background: {
      default: "#f6f8f7",
    },
  },
  shape: {
    borderRadius: 8,
  },
});

export function App(): JSX.Element {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </ThemeProvider>
  );
}
