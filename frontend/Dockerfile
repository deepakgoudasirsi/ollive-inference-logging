FROM node:20-alpine

WORKDIR /app

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY package.json /app/package.json
RUN npm install

COPY index.html /app/index.html
COPY vite.config.ts /app/vite.config.ts
COPY tsconfig.json /app/tsconfig.json
COPY src /app/src

EXPOSE 5173

CMD ["npm", "run", "dev"]

