import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from "@mui/material";

interface InstructionDialogProps {
  content: string;
  onClose: () => void;
  open: boolean;
  title: string;
}

function renderInstructionLine(line: string, index: number): JSX.Element | null {
  const trimmed = line.trim();
  if (trimmed.length === 0) {
    return null;
  }
  if (trimmed.startsWith("# ")) {
    return (
      <Typography component="h2" key={index} variant="h6">
        {trimmed.slice(2)}
      </Typography>
    );
  }
  if (trimmed.startsWith("## ")) {
    return (
      <Typography component="h3" key={index} sx={{ mt: 1 }} variant="subtitle1">
        {trimmed.slice(3)}
      </Typography>
    );
  }
  if (trimmed.startsWith("- ")) {
    return (
      <Box component="ul" key={index} sx={{ my: 0, pl: 3 }}>
        <Typography component="li" variant="body2">
          {trimmed.slice(2)}
        </Typography>
      </Box>
    );
  }
  return (
    <Typography key={index} variant="body2">
      {trimmed}
    </Typography>
  );
}

export function InstructionDialog({
  content,
  onClose,
  open,
  title,
}: InstructionDialogProps): JSX.Element {
  return (
    <Dialog fullWidth maxWidth="md" onClose={onClose} open={open}>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent dividers>
        <Stack
          component="article"
          spacing={1}
        >
          {content.split("\n").map(renderInstructionLine)}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Закрыть</Button>
      </DialogActions>
    </Dialog>
  );
}
