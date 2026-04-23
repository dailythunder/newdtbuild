from dtlib.state_io import load_all


def main() -> None:
    data = load_all()
    active = data['content_state'].get('lanes', {}).get('bolts', {}).get('active', False)
    print('Bolts roundup is intentionally inactive in this clean decentralized build.')
    print(f'bolts_active={active}')


if __name__ == '__main__':
    main()
