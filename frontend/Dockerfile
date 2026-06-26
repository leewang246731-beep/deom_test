FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build:admin && npm run build:merchant && npm run build:service

FROM nginx:alpine
COPY --from=build /app/dist-admin /usr/share/nginx/html/admin
COPY --from=build /app/dist-merchant /usr/share/nginx/html/merchant
COPY --from=build /app/dist-service /usr/share/nginx/html/service
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
