import './globals.css'

export const metadata = {
  title: 'LoRA Person MVP',
  description: 'Train LoRA models and generate images',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
